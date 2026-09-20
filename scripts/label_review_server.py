"""Zero-dependency local browser tool for confirming boxes and video events."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CLASSES = {"electric_bicycle", "person", "bicycle", "motorcycle"}
EVENT_TYPES = {"safe_pass", "near_miss", "conflict"}


def clamp_box(box, width, height):
    values = [float(value) for value in box]
    if len(values) != 4 or width <= 0 or height <= 0:
        raise ValueError("box must contain four coordinates and dimensions must be positive")
    x1, x2 = sorted((max(0.0, min(values[0], width)), max(0.0, min(values[2], width))))
    y1, y2 = sorted((max(0.0, min(values[1], height)), max(0.0, min(values[3], height))))
    return [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)]


def validate_annotation(payload):
    errors = []
    if not isinstance(payload, dict) or not isinstance(payload.get("image"), str):
        return ["image must be a string"]
    if payload.get("event_type") not in EVENT_TYPES:
        errors.append(f"event_type must be one of {sorted(EVENT_TYPES)}")
    boxes = payload.get("boxes")
    if not isinstance(boxes, list):
        return errors + ["boxes must be a list"]
    for index, item in enumerate(boxes):
        if not isinstance(item, dict) or item.get("class") not in CLASSES:
            errors.append(f"boxes[{index}].class is invalid")
        box = item.get("box") if isinstance(item, dict) else None
        if not isinstance(box, list) or len(box) != 4:
            errors.append(f"boxes[{index}].box must contain four coordinates")
        else:
            try:
                [float(value) for value in box]
            except (TypeError, ValueError):
                errors.append(f"boxes[{index}].box must be numeric")
    return errors


def build_items(manifest_path, candidates_path=None, only_candidates=False):
    with Path(manifest_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    candidates = {}
    if candidates_path:
        payload = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
        for detection in payload.get("detections", []):
            candidates.setdefault(detection["image"], []).append(detection)
    items = []
    for row in rows:
        image = row["image"]
        if only_candidates and image not in candidates:
            continue
        items.append({
            "image": image,
            "video_id": row.get("video_id", ""),
            "frame": int(row.get("frame", 0)),
            "timestamp_s": float(row.get("timestamp_s", 0)),
            "candidates": candidates.get(image, []),
        })
    return items


HTML = r"""<!doctype html><meta charset="utf-8"><title>BlindNav 标注审核</title>
<style>
body { font-family: system-ui, sans-serif; margin: 16px; background: #f4f5f7; }
#bar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
button, select { font-size:16px; padding:6px 10px; }
#stage { position:relative; display:inline-block; margin-top:12px; background:#111; }
#img { display:block; max-width:90vw; max-height:78vh; }
#canvas { position:absolute; left:0; top:0; cursor:crosshair; }
#info { margin-top:8px; white-space:pre-wrap; }
.hint { color:#555; }
</style>
<div id="bar"><button onclick="move(-1)">上一帧</button><button onclick="move(1)">下一帧</button>
<button onclick="save()">保存标注</button>
<label>类别 <select id="cls"><option>electric_bicycle</option><option>person</option><option>bicycle</option><option>motorcycle</option></select></label>
<label>事件 <select id="event"><option>safe_pass</option><option>near_miss</option><option>conflict</option></select></label><span id="counter"></span></div>
<div class="hint">黄色框=模型候选，红色框=人工框。拖动鼠标画框；右键清空当前人工框。</div>
<div id="stage"><img id="img"><canvas id="canvas"></canvas></div><div id="info"></div>
<script>
let items=[], index=0, manual=[], drawing=null;
const img=document.getElementById('img'), canvas=document.getElementById('canvas'), ctx=canvas.getContext('2d');
async function init(){items=await(await fetch('/api/items')).json();if(items.length)show();}
function point(e){const r=canvas.getBoundingClientRect();return[(e.clientX-r.left)*img.naturalWidth/canvas.width,(e.clientY-r.top)*img.naturalHeight/canvas.height];}
function draw(){if(!img.naturalWidth)return;canvas.width=img.clientWidth;canvas.height=img.clientHeight;ctx.clearRect(0,0,canvas.width,canvas.height);const sx=canvas.width/img.naturalWidth,sy=canvas.height/img.naturalHeight;
const box=(b,c,l)=>{ctx.strokeStyle=c;ctx.lineWidth=3;ctx.strokeRect(b[0]*sx,b[1]*sy,(b[2]-b[0])*sx,(b[3]-b[1])*sy);ctx.fillStyle=c;ctx.font='14px sans-serif';ctx.fillText(l,b[0]*sx,Math.max(14,b[1]*sy-4));};
(items[index].candidates||[]).forEach(d=>box(d.box,'#ffd400',d.source_class+' '+d.confidence));manual.forEach(d=>box(d.box,'#ff3b30',d.class));if(drawing)box(drawing,'#00e676','new');}
function fit(){draw();}
function show(){const it=items[index];manual=(it.saved&&it.saved.boxes)||[];document.getElementById('event').value=(it.saved&&it.saved.event_type)||'safe_pass';img.onload=fit;img.src='/api/image?name='+encodeURIComponent(it.image);document.getElementById('counter').textContent=`${index+1}/${items.length}`;document.getElementById('info').textContent=`${it.video_id} frame=${it.frame} t=${it.timestamp_s}s candidates=${it.candidates.length}`;}
function move(d){if(!items.length)return;index=Math.max(0,Math.min(items.length-1,index+d));show();}
canvas.addEventListener('mousedown',e=>{if(e.button===0){drawing=[...point(e),...point(e)];draw();}});
canvas.addEventListener('mousemove',e=>{if(drawing){const p=point(e);drawing[2]=p[0];drawing[3]=p[1];draw();}});
canvas.addEventListener('mouseup',e=>{if(!drawing)return;const b=drawing;drawing=null;const x1=Math.min(b[0],b[2]),y1=Math.min(b[1],b[3]),x2=Math.max(b[0],b[2]),y2=Math.max(b[1],b[3]);if(x2-x1>4&&y2-y1>4)manual.push({class:document.getElementById('cls').value,box:[x1,y1,x2,y2]});draw();});
canvas.addEventListener('contextmenu',e=>{e.preventDefault();manual=[];draw();});
async function save(){const it=items[index],payload={image:it.image,event_type:document.getElementById('event').value,boxes:manual};const r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const j=await r.json();if(!j.ok)alert(j.errors.join('\n'));else{it.saved=payload;alert('已保存');}}
window.addEventListener('resize',fit);init();
</script>"""


class ReviewServer:
    def __init__(self, items, output_path, frames_root):
        self.items = items
        self.output_path = Path(output_path)
        self.frames_root = Path(frames_root).resolve()
        self.saved = {}
        if self.output_path.is_file():
            payload = json.loads(self.output_path.read_text(encoding="utf-8"))
            self.saved = {item["image"]: item for item in payload.get("annotations", [])}
        for item in self.items:
            item["saved"] = self.saved.get(item["image"])

    def save(self, payload):
        errors = validate_annotation(payload)
        if errors:
            return {"ok": False, "errors": errors}
        target = Path(payload["image"]).resolve()
        if self.frames_root not in target.parents:
            return {"ok": False, "errors": ["image is outside frames root"]}
        self.saved[payload["image"]] = payload
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps({"annotations": list(self.saved.values())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"ok": True}


def serve(manifest, frames_root, output, candidates=None, only_candidates=False, port=8765):
    items = build_items(manifest, candidates, only_candidates)
    store = ReviewServer(items, output, frames_root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = HTML.encode("utf-8"); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if parsed.path == "/api/items":
                body = json.dumps(store.items, ensure_ascii=False).encode("utf-8"); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if parsed.path == "/api/image":
                name = parse_qs(parsed.query).get("name", [""])[0]; target = Path(name).resolve()
                if store.frames_root not in target.parents or not target.is_file(): self.send_error(404); return
                body = target.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            self.send_error(404)

        def do_POST(self):
            if self.path != "/api/save": self.send_error(404); return
            try: payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            except json.JSONDecodeError: payload = {}
            body = json.dumps(store.save(payload), ensure_ascii=False).encode("utf-8"); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def log_message(self, *_): pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"review items={len(items)} url=http://127.0.0.1:{port}/ output={output}")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Open local annotation review UI")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--frames-root", type=Path, required=True)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--output", type=Path, default=Path("annotations/local_review.json"))
    parser.add_argument("--only-candidates", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.manifest, args.frames_root, args.output, args.candidates, args.only_candidates, args.port)


if __name__ == "__main__":
    main()
