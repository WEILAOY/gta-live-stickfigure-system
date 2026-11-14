"""Desktop entry point; optional AI dependencies live in the local venv."""
from pathlib import Path
import argparse
import logging
import sys
import traceback

from stickfigure.app import Application,DETECTION_RATES,ROAD_RATES
from stickfigure.detection import MODEL_PROFILES


def main():
    parser = argparse.ArgumentParser(description="实时火柴人画面系统")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--video", help="预加载本地视频（静音预览）")
    parser.add_argument("--obs", action="store_true", help="连接 OBS 虚拟摄像机")
    parser.add_argument("--video-smoke-test", metavar="PATH", help="使用真实视频执行集成检查")
    parser.add_argument("--detect-smoke-test", metavar="PATH", help="使用真实模型验证人车检测与重绘")
    parser.add_argument('--workflow-smoke-test',metavar='PATH',help='验证主角绑定、暂停保留及道路轮廓')
    parser.add_argument('--performance-smoke-test',metavar='PATH',help='并行测量人车与路缘的实际检测频率')
    parser.add_argument("--start-at",type=float,default=0,help="预加载视频的起始秒数")
    parser.add_argument('--detect-hz',type=int,choices=DETECTION_RATES,help='人车检测目标频率')
    parser.add_argument('--road-hz',type=int,choices=ROAD_RATES,help='道路/建筑分析目标频率')
    parser.add_argument('--output-fps',type=int,choices=(15,30,60),help='输出刷新目标帧率')
    parser.add_argument('--model-profile',choices=tuple(MODEL_PROFILES),help='人车识别档位')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    try:
        app = Application(base, smoke_test=args.smoke_test or bool(args.video_smoke_test or args.detect_smoke_test or args.workflow_smoke_test or args.performance_smoke_test),
                          initial_video=args.performance_smoke_test or args.workflow_smoke_test or args.detect_smoke_test or args.video_smoke_test or args.video,
                          video_smoke=bool(args.video_smoke_test),detection_smoke=bool(args.detect_smoke_test),
                          initial_position=args.start_at,road_smoke=bool(args.workflow_smoke_test or args.performance_smoke_test),performance_smoke=bool(args.performance_smoke_test))
        for value,var in ((args.detect_hz,app.detect_rate_var),(args.road_hz,app.road_rate_var),(args.output_fps,app.fps_var)):
            if value is not None:
                var.set(str(value))
        if args.model_profile is not None:
            app.model_profile_var.set(args.model_profile)
            app._model_changed()
        if args.obs:
            from stickfigure.app import SOURCES
            app.source_var.set(SOURCES[1])
            app._source_changed()
            app.start()
        app.mainloop()
        return 0 if not app.test_failed else 1
    except Exception:
        logging.exception("Application failed")
        (base / "runtime").mkdir(exist_ok=True)
        (base / "runtime" / "启动错误.txt").write_text(traceback.format_exc(), encoding="utf-8")
        if not (args.smoke_test or args.video_smoke_test or args.detect_smoke_test or args.workflow_smoke_test or args.performance_smoke_test):
            from tkinter import messagebox
            messagebox.showerror("启动失败", "请查看软件目录 runtime/启动错误.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
