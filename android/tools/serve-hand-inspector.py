"""Local development viewer; never packaged. See TextToSignHandFix.md."""
import argparse
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlparse

parser=argparse.ArgumentParser()
parser.add_argument('--before',type=Path,required=True)
parser.add_argument('--recording',type=Path)
parser.add_argument('--port',type=int,default=9042)
args=parser.parse_args()
android=Path(__file__).resolve().parents[1]
assert args.before.is_file()
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Diagnostics must never compare a corrected file against stale bytes.
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def translate_path(self,url):
        path=unquote(urlparse(url).path)
        fixed={'/before.glb':args.before,
               '/after.glb':android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb',
               '/':Path(__file__).with_name('hand_pose_inspector.html'),
               '/inspector.html':Path(__file__).with_name('hand_pose_inspector.html')}
        if args.recording:fixed['/recording.mp4']=args.recording
        if path in fixed:return str(fixed[path].resolve())
        if path.startswith('/assets/'):
            relative=Path(path[len('/assets/'):])
            if not relative.is_absolute() and '..' not in relative.parts:
                for folder in ['aslPilot','aslAlphabet','aslOriginalWords','main']:
                    asset=android/f'app/src/{folder}/assets'/relative
                    if asset.is_file():return str(asset)
        return str(android/'tools/nonexistent-inspection-resource')
print(f'Local hand inspector: http://127.0.0.1:{args.port}/',flush=True)
ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
