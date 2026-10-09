// P7DR2: same numerical algorithm as P7dr1Math. No fast-math, contraction or threads.
#include <jni.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <vector>
#include <array>

namespace {
struct Kernel {
    int w,h,row,pixel,rotation,ow,oh,rw,rh,left,top;
    size_t bytes;
    std::vector<uint8_t> raw;
    std::vector<int> a,b,d,e;
    std::array<float,384> wx{},wy{};
    std::array<uint8_t,9216> admissible{};
    std::array<int,50> peaks{};
    std::array<float,50> maxima{},confidence{};
    std::array<float,100> xy{},source{};
    std::array<float,2> identity{};
    Kernel(int width,int height,int stride,int ps,int rot):w(width),h(height),row(stride),pixel(ps),rotation(rot) {
        if(w<=0||h<=0||w>16384||h>16384||pixel<4||int64_t(row)<int64_t(w-1)*pixel+4||
           !(rot==0||rot==90||rot==180||rot==270))throw std::invalid_argument("GEOMETRY_INVALID");
        bytes=size_t(h-1)*row+size_t(w-1)*pixel+3;
        if(bytes>256*1024*1024)throw std::invalid_argument("SOURCE_SIZE_INVALID");
        ow=(rot==90||rot==270)?h:w;oh=(rot==90||rot==270)?w:h;
        double scale=std::min(384.0/ow,384.0/oh);
        rw=std::max(1,int(std::floor(ow*scale+.5)));rh=std::max(1,int(std::floor(oh*scale+.5)));
        left=(384-rw)/2;top=(384-rh)/2;
        raw.resize(bytes);a.assign(384*384,-1);b.resize(a.size());d.resize(a.size());e.resize(a.size());
        for(int y=top;y<top+rh;++y) {
            double sy=std::clamp(inverseY(y),0.0,double(oh-1));int y0=int(std::floor(sy)),y1=std::min(y0+1,oh-1);
            wy[y]=float(sy-y0);
            for(int x=left;x<left+rw;++x) {
                double sx=std::clamp(inverseX(x),0.0,double(ow-1));int x0=int(std::floor(sx)),x1=std::min(x0+1,ow-1);
                wx[x]=float(sx-x0);int k=y*384+x;
                a[k]=offset(x0,y0);b[k]=offset(x1,y0);d[k]=offset(x0,y1);e[k]=offset(x1,y1);
            }
        }
        for(int i=0;i<96;++i)for(int j=0;j<96;++j){
            double x=inverseX(4*(j+.5)-.5),y=inverseY(4*(i+.5)-.5);
            admissible[i*96+j]=(x>=0&&x<=ow-1&&y>=0&&y<=oh-1);
        }
    }
    double inverseX(double x)const{return (x-left+.5)*ow/rw-.5;}
    double inverseY(double y)const{return (y-top+.5)*oh/rh-.5;}
    int offset(int x,int y)const {
        switch(rotation){case 90:return(h-1-x)*row+y*pixel;
        case 180:return(h-1-y)*row+(w-1-x)*pixel;
        case 270:return x*row+(w-1-y)*pixel;default:return y*row+x*pixel;}
    }
    void preprocess(const uint8_t* input,float* out) {
        std::memcpy(raw.data(),input,bytes);
        for(int y=0;y<384;++y)for(int x=0;x<384;++x){
            int k=y*384+x,aa=a[k];
            if(aa<0){*out++=0;*out++=0;*out++=0;continue;}
            int bb=b[k],dd=d[k],ee=e[k];float fx=wx[x],fy=wy[y];
            for(int c=0;c<3;++c){
                float av=raw[aa+c],bv=raw[bb+c],dv=raw[dd+c],ev=raw[ee+c];
                float v=(av*(1-fx)+bv*fx)*(1-fy)+(dv*(1-fx)+ev*fx)*fy;
                *out++=(v-127.5f)/127.5f;
            }
        }
    }
    static float sigmoid(double v){return float(v>=0?1/(1+std::exp(-v)):std::exp(v)/(1+std::exp(v)));}
    void decode(const float* heat,const float* ids){
        if(std::none_of(admissible.begin(),admissible.end(),[](uint8_t v){return v!=0;}))throw std::invalid_argument("INPUT_TRANSFORM_INVALID");
        if(!std::isfinite(ids[0])||!std::isfinite(ids[1]))throw std::invalid_argument("NATIVE_OUTPUT_INVALID");
        maxima.fill(-std::numeric_limits<float>::infinity());peaks.fill(-1);
        int k=0;
        for(int cell=0;cell<9216;++cell)for(int p=0;p<50;++p){
            float v=heat[k++];
            if(!std::isfinite(v))throw std::invalid_argument("NATIVE_OUTPUT_INVALID");
            if(admissible[cell]&&v>maxima[p]){maxima[p]=v;peaks[p]=cell;}
        }
        for(int p=0;p<50;++p){
            int px=peaks[p]%96,py=peaks[p]/96;double sum=0,sx=0,sy=0;
            for(int i=std::max(0,py-1);i<=std::min(95,py+1);++i)
                for(int j=std::max(0,px-1);j<=std::min(95,px+1);++j){
                    if(!admissible[i*96+j])continue;
                    double weight=std::exp(double(heat[(i*96+j)*50+p])-maxima[p]);
                    sum+=weight;sx+=j*weight;sy+=i*weight;
                }
            xy[p*2]=float(4*(sx/sum+.5)-.5);xy[p*2+1]=float(4*(sy/sum+.5)-.5);
            confidence[p]=sigmoid(maxima[p]);
        }
        identity[0]=sigmoid(ids[0]);identity[1]=sigmoid(ids[1]);
    }
    void restore(){for(int p=0;p<50;++p){source[p*2]=float(inverseX(xy[p*2]));source[p*2+1]=float(inverseY(xy[p*2+1]));
        if(!std::isfinite(source[p*2])||!std::isfinite(source[p*2+1]))throw std::invalid_argument("SOURCE_OUTPUT_NONFINITE");}}
};
void error(JNIEnv* env,const char* msg){env->ThrowNew(env->FindClass("java/lang/IllegalArgumentException"),msg);}
Kernel* kernel(jlong handle){if(!handle)throw std::invalid_argument("CLOSED_NATIVE_HANDLE");return reinterpret_cast<Kernel*>(handle);}
struct Floats {JNIEnv* env;jfloatArray array;jfloat* data;
    Floats(JNIEnv* e,jfloatArray a,int n):env(e),array(a),data(nullptr){
        if(!a||env->GetArrayLength(a)!=n)throw std::invalid_argument("ARRAY_SHAPE_INVALID");
        data=env->GetFloatArrayElements(a,nullptr);if(!data)throw std::runtime_error("JNI_ARRAY_UNAVAILABLE");}
    ~Floats(){if(data)env->ReleaseFloatArrayElements(array,data,JNI_ABORT);}
};
}
#define JNI_FN(name) Java_com_example_apphear_p7dr2_P7dr2Native_##name
extern "C" JNIEXPORT jlong JNICALL JNI_FN(create)(JNIEnv* env,jobject,jint w,jint h,jint row,jint pixel,jint rot){
    try{return reinterpret_cast<jlong>(new Kernel(w,h,row,pixel,rot));}catch(const std::exception& e){error(env,e.what());return 0;}}
extern "C" JNIEXPORT void JNICALL JNI_FN(destroy)(JNIEnv*,jobject,jlong h){delete reinterpret_cast<Kernel*>(h);}
extern "C" JNIEXPORT void JNICALL JNI_FN(preprocess)(JNIEnv* env,jobject,jlong h,jobject src,jint base,jint remaining,jobject out){
    try{auto* k=kernel(h);auto* p=static_cast<uint8_t*>(env->GetDirectBufferAddress(src));auto* q=static_cast<float*>(env->GetDirectBufferAddress(out));
        auto cap=env->GetDirectBufferCapacity(src);
        if(!p||!q||base<0||remaining<0||size_t(remaining)<k->bytes||int64_t(base)+remaining>cap||env->GetDirectBufferCapacity(out)!=384*384*3*4)
            throw std::invalid_argument("DIRECT_BUFFER_BOUNDS_INVALID");
        k->preprocess(p+base,q);
    }catch(const std::exception& e){error(env,e.what());}}
extern "C" JNIEXPORT void JNICALL JNI_FN(decode)(JNIEnv* env,jobject,jlong h,jfloatArray heat,jfloatArray ids,jfloatArray xy,jfloatArray conf,jfloatArray identity,jintArray peaks){
    try{auto* k=kernel(h);
        if(env->GetArrayLength(xy)!=100||env->GetArrayLength(conf)!=50||env->GetArrayLength(identity)!=2||env->GetArrayLength(peaks)!=50)throw std::invalid_argument("READOUT_SHAPE_INVALID");
        {Floats a(env,heat,460800),b(env,ids,2);k->decode(a.data,b.data);}
        env->SetFloatArrayRegion(xy,0,100,k->xy.data());env->SetFloatArrayRegion(conf,0,50,k->confidence.data());
        env->SetFloatArrayRegion(identity,0,2,k->identity.data());env->SetIntArrayRegion(peaks,0,50,k->peaks.data());
    }catch(const std::exception& e){error(env,e.what());}}
extern "C" JNIEXPORT void JNICALL JNI_FN(restore)(JNIEnv* env,jobject,jlong h,jfloatArray out){
    try{auto* k=kernel(h);if(env->GetArrayLength(out)!=100)throw std::invalid_argument("RESTORE_SHAPE_INVALID");k->restore();env->SetFloatArrayRegion(out,0,100,k->source.data());}
    catch(const std::exception& e){error(env,e.what());}}
extern "C" JNIEXPORT jintArray JNICALL JNI_FN(geometry)(JNIEnv* env,jobject,jlong h){
    try{auto* k=kernel(h);int values[]={k->ow,k->oh,k->rw,k->rh,k->left,k->top};auto out=env->NewIntArray(6);env->SetIntArrayRegion(out,0,6,values);return out;}
    catch(const std::exception& e){error(env,e.what());return nullptr;}}
extern "C" JNIEXPORT jbyteArray JNICALL JNI_FN(allowed)(JNIEnv* env,jobject,jlong h){
    try{auto* k=kernel(h);auto out=env->NewByteArray(9216);env->SetByteArrayRegion(out,0,9216,reinterpret_cast<jbyte*>(k->admissible.data()));return out;}
    catch(const std::exception& e){error(env,e.what());return nullptr;}}
