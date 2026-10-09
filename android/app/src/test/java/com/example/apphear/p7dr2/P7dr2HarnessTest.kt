package com.example.apphear.p7dr2

import com.example.apphear.p7dr1.P7dr1Preprocess
import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.util.Random

class P7dr2HarnessTest {
    @Test fun v0UsesUnchangedReference() {
        val source=ByteBuffer.allocateDirect(640*480*4)
        val bytes=ByteArray(source.capacity());Random(707).nextBytes(bytes);source.put(bytes);source.rewind()
        val ref=P7dr1Preprocess(640,480,2560,4,270)
        P7dr2Path(0,640,480,2560,4,270).use {v0->
            ref.run(source);v0.preprocess(source)
            for(k in 0 until 442368)assertEquals(ref.input.getFloat(k*4),v0.input.getFloat(k*4),0f)
            val heat=FloatArray(460800);val identity=FloatArray(2)
            v0.decode(heat,identity);v0.restore()
        }
    }
    @Test fun rejectsUndeclaredVariant() {
        assertThrows(IllegalArgumentException::class.java){P7dr2Path(4,640,480,2560,4,270)}
    }
}
