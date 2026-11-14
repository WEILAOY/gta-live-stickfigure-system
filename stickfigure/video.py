"""Bounded, asynchronous FFmpeg preview. No Tk calls on the worker thread."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import json
import queue
import shutil
import subprocess
import threading
import time


@dataclass(frozen=True)
class VideoInfo:
    path: str
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool


@dataclass(frozen=True)
class VideoFrame:
    generation: int
    timestamp: float
    width: int
    height: int
    pixels: bytes

    def ppm(self):
        return f"P6\n{self.width} {self.height}\n255\n".encode("ascii") + self.pixels


def probe_video(path):
    executable = shutil.which("ffprobe")
    if not executable or not shutil.which("ffmpeg"):
        raise RuntimeError("未找到 FFmpeg / ffprobe，请检查安装和 PATH。")
    path = Path(path).resolve(strict=True)
    proc = subprocess.run([executable,"-v","error","-show_streams","-show_format","-of","json",str(path)],
                          capture_output=True,timeout=15,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if proc.returncode:
        raise RuntimeError("视频信息读取失败："+proc.stderr.decode("utf-8",errors="replace")[-400:])
    data = json.loads(proc.stdout)
    streams = data.get("streams",[])
    video = next((s for s in streams if s.get("codec_type")=="video"),None)
    if not video:
        raise ValueError("文件中没有视频轨道。")
    width,height = int(video["width"]),int(video["height"])
    duration = float(data.get("format",{}).get("duration") or video.get("duration") or 0)
    try:
        fps = float(Fraction(video.get("avg_frame_rate","0/1")))
    except (ValueError,ZeroDivisionError):
        fps = 0
    if width<=0 or height<=0 or duration<=0:
        raise ValueError("视频尺寸或时长无效；本版只支持可定位的有限时长视频。")
    return VideoInfo(str(path),width,height,fps or 30,duration,
                     any(s.get("codec_type")=="audio" for s in streams))


class VideoPlayer:
    """A request generation invalidates old frames, probe events and decoders.

    Preview is normalized to at most 30 FPS; timestamps describe that preview
    timeline, not authoritative original VFR frame PTS. Audio is not played.
    """
    def __init__(self):
        self.frames = queue.Queue(maxsize=2)
        self.events = queue.Queue(maxsize=32)
        self._condition = threading.Condition()
        self._pending = None
        self._generation = 0
        self._closed = False
        self._process = None
        self._cache = None
        self.frame_observer=None
        self._thread = threading.Thread(target=self._run,name="video-preview",daemon=True)
        self._thread.start()

    @property
    def generation(self):
        with self._condition:
            return self._generation

    @property
    def worker_alive(self):
        return self._thread.is_alive()

    def request(self,path,position=0,playing=False):
        with self._condition:
            if self._closed:
                raise RuntimeError("Video player is closed")
            self._generation += 1
            self._pending = (self._generation,str(path),max(0,float(position)),bool(playing),False)
            self._kill_decoder()
            self._condition.notify_all()
            return self._generation

    def request_obs(self):
        with self._condition:
            if self._closed:
                raise RuntimeError("Video player is closed")
            self._generation += 1
            self._pending = (self._generation,"OBS Virtual Camera",0,True,True)
            self._kill_decoder()
            self._condition.notify_all()
            return self._generation

    def cancel(self):
        with self._condition:
            self._generation += 1
            self._pending = None
            self._kill_decoder()
            self._condition.notify_all()

    def close(self):
        with self._condition:
            self._closed = True
            self._generation += 1
            self._kill_decoder()
            self._condition.notify_all()

    def _kill_decoder(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.kill()
            except OSError:
                pass

    @staticmethod
    def _put_latest(target,item):
        try:
            target.put_nowait(item)
        except queue.Full:
            try:
                target.get_nowait()
            except queue.Empty:
                pass
            try:
                target.put_nowait(item)
            except queue.Full:
                pass

    def _event(self,generation,kind,payload=None):
        if generation==self.generation:
            self._put_latest(self.events,(generation,kind,payload))

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._pending is not None or self._closed)
                if self._closed:
                    return
                generation,path,position,playing,live = self._pending
                self._pending = None
            try:
                if live:
                    self._decode(generation,VideoInfo(path,960,540,30,0,False),0,True,live=True)
                    continue
                # Re-probe on file changes, but not on every pause and seek.
                stat = Path(path).stat()
                key = (path,stat.st_size,stat.st_mtime_ns)
                if self._cache is None or self._cache[0]!=key:
                    self._cache = (key,probe_video(path))
                info = self._cache[1]
                if generation!=self.generation:
                    continue
                self._event(generation,"loaded",info)
                self._decode(generation,info,min(position,max(0,info.duration-.05)),playing)
            except Exception as exc:
                self._event(generation,"error",str(exc))

    def _decode(self,generation,info,position,playing,live=False):
        width = min(960,info.width)
        height = max(2,round(info.height*width/info.width))
        fps = min(30,info.fps)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("未找到 FFmpeg，请检查 PATH。")
        cmd = [ffmpeg,"-hide_banner","-loglevel","error","-nostdin"]
        if live:
            cmd += ["-rtbufsize","24M","-f","dshow","-i",f"video={info.path}"]
            filters = f"fps=30,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        else:
            cmd += ["-ss",f"{position:.6f}","-i",info.path]
            filters = f"scale={width}:{height},fps={fps:.8f}"
        cmd += ["-map","0:v:0","-an","-sn","-dn","-filter_threads","2","-vf",filters,
                "-threads","2","-pix_fmt","rgb24","-f","rawvideo","pipe:1"]
        proc = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        with self._condition:
            self._process = proc
            if generation!=self._generation or self._closed:
                self._kill_decoder()
        size = width*height*3
        index = 0
        anchor = None
        try:
            while generation==self.generation:
                chunks = bytearray()
                while len(chunks)<size:
                    part = proc.stdout.read(size-len(chunks))
                    if not part:
                        break
                    chunks.extend(part)
                if generation!=self.generation:
                    return
                if len(chunks)!=size:
                    code = proc.wait(timeout=3)
                    if live:
                        self._event(generation,"error",f"OBS 虚拟摄像机输入中断（退出码 {code}）。请检查 OBS 后重新连接。")
                    elif code or index==0:
                        self._event(generation,"error",f"视频解码失败或没有可读取帧（退出码 {code}）。")
                    else:
                        self._event(generation,"ended",info.duration)
                    return
                if anchor is None:
                    anchor = time.perf_counter()
                    if live:
                        self._event(generation,"loaded",info)
                if playing and not live:
                    deadline = anchor+index/fps
                    with self._condition:
                        self._condition.wait_for(lambda:generation!=self._generation or self._closed,
                                                 timeout=max(0,deadline-time.perf_counter()))
                    if generation!=self.generation:
                        return
                timestamp = time.perf_counter()-anchor if live else min(position+index/fps,info.duration)
                frame = VideoFrame(generation,timestamp,width,height,bytes(chunks))
                observer=self.frame_observer
                if observer is not None:observer(frame)
                self._put_latest(self.frames,frame)
                index += 1
                if not playing:
                    return
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=3)
            if proc.stdout:
                proc.stdout.close()
            with self._condition:
                if self._process is proc:
                    self._process = None
