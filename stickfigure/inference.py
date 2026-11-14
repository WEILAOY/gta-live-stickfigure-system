"""Optional Windows DirectML acceleration, CPU fallback and adapter discovery."""
import os
import threading
from functools import lru_cache

_gpu_lock=threading.RLock()

class GpuSession:
    """Serialize DML sessions: this laptop driver crashed on concurrent runs."""
    def __init__(self,session):self.session=session
    def __getattr__(self,name):return getattr(self.session,name)
    def run(self,*args,**kwargs):
        with _gpu_lock:return self.session.run(*args,**kwargs)

@lru_cache(maxsize=1)
def windows_adapters():
    if os.name!='nt':return ()
    import ctypes as c
    import uuid
    class Guid(c.Structure):
        _fields_=[('a',c.c_uint32),('b',c.c_uint16),('d',c.c_uint16),('e',c.c_ubyte*8)]
    class Desc(c.Structure):
        _fields_=[('name',c.c_wchar*128),('vendor',c.c_uint32),('device',c.c_uint32),
                  ('subsystem',c.c_uint32),('revision',c.c_uint32),
                  ('video',c.c_size_t),('system',c.c_size_t),('shared',c.c_size_t),
                  ('luid_low',c.c_uint32),('luid_high',c.c_int32),('flags',c.c_uint32)]
    def call(ptr,index,restype,*args):
        vtable=c.cast(ptr,c.POINTER(c.POINTER(c.c_void_p))).contents
        return c.WINFUNCTYPE(restype,c.c_void_p,*args)(vtable[index])
    factory=c.c_void_p()
    create=c.WinDLL('dxgi').CreateDXGIFactory1
    create.argtypes=[c.POINTER(Guid),c.POINTER(c.c_void_p)];create.restype=c.c_int32
    iid=Guid.from_buffer_copy(uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le)
    if create(c.byref(iid),c.byref(factory))<0:return ()
    result=[]
    try:
        for index in range(16):
            adapter=c.c_void_p()
            if call(factory,12,c.c_int32,c.c_uint,c.POINTER(c.c_void_p))(factory,index,c.byref(adapter))<0:break
            try:
                desc=Desc()
                if call(adapter,10,c.c_int32,c.POINTER(Desc))(adapter,c.byref(desc))>=0 and not desc.flags&2:
                    result.append(dict(index=index,name=desc.name,vendor=desc.vendor,video_bytes=desc.video))
            finally:call(adapter,2,c.c_uint32)(adapter)
    finally:call(factory,2,c.c_uint32)(factory)
    return tuple(result)

def create_session(path,prefer_gpu=True,dimensions=None):
    import onnxruntime as ort
    options=ort.SessionOptions()
    options.intra_op_num_threads=2;options.inter_op_num_threads=1
    options.add_session_config_entry('session.intra_op.allow_spinning','0')
    options.add_session_config_entry('session.inter_op.allow_spinning','0')
    for name,value in (dimensions or {}).items():
        options.add_free_dimension_override_by_name(name,value)
    if prefer_gpu and os.environ.get('STICKFIGURE_CPU')!='1' and 'DmlExecutionProvider' in ort.get_available_providers():
        try:
            adapters=windows_adapters()
            adapter=next((a for a in adapters if a['vendor']==0x10de),adapters[0] if adapters else None)
            index=adapter['index'] if adapter else 0
            options.enable_mem_pattern=False
            options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
            with _gpu_lock:
                session=ort.InferenceSession(str(path),sess_options=options,
                             providers=[('DmlExecutionProvider',{'device_id':str(index)}),'CPUExecutionProvider'])
            if 'DmlExecutionProvider' in session.get_providers():
                return GpuSession(session),'GPU · DirectML · '+(adapter['name'] if adapter else str(index))
        except Exception:
            # Missing/incompatible GPU is a reversible fallback, not a failed source.
            pass
    return ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']),'CPU · ONNX Runtime'
