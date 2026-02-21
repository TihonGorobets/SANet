
/* ══════════════════════════════════════════════════════════════════════════
   WHITEBOARD ENGINE v2 — Scene-Graph Architecture
   ══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ─────────────────────────────────────────────────────────────────────────
     DOM REFS
  ───────────────────────────────────────────────────────────────────────── */
  const overlay      = document.getElementById('wbOverlay');
  const canvasArea   = document.getElementById('wbCanvasArea');
  const canvas       = document.getElementById('wbCanvas');
  const ctx          = canvas.getContext('2d');
  const stickyLayer  = document.getElementById('stickyLayer');
  const openBtn      = document.getElementById('wbOpenBtn');
  const closeBtn     = document.getElementById('wbCloseBtn');
  const toolBtns     = document.querySelectorAll('.wb-tool-btn[data-tool]');
  const colorSwatch  = document.getElementById('wbColorSwatch');
  const sizeSlider   = document.getElementById('wbSizeSlider');
  const sizeVal      = document.getElementById('wbSizeVal');
  const addStickyBtn = document.getElementById('wbAddSticky');
  const undoBtn      = document.getElementById('wbUndo');
  const redoBtn      = document.getElementById('wbRedo');
  const saveBtn      = document.getElementById('wbSave');
  const exportBtn    = document.getElementById('wbExport');
  const clearBtn     = document.getElementById('wbClear');
  const zoomPctEl    = document.getElementById('wbZoomPct');
  const toolNameEl   = document.getElementById('wbToolName');
  const itemCountEl  = document.getElementById('wbItemCount');
  const toastEl      = document.getElementById('wbToast');
  const paletteEl    = document.getElementById('wbPalette');
  const paletteGrid  = document.getElementById('wbPaletteGrid');
  const customColorEl= document.getElementById('wbCustomColor');

  /* ─────────────────────────────────────────────────────────────────────────
     CONSTANTS
  ───────────────────────────────────────────────────────────────────────── */
  const STORAGE_KEY = 'san-wb-v4';
  const MAX_HIST    = 60;
  const HANDLE_R    = 6;   // resize handle radius px (screen space)
  const HIT_THRESH  = 8;   // px tolerance for stroke hit-test
  const TOOL_LABELS = {
    select:'Select', pen:'Pen', highlighter:'Highlighter',
    eraser:'Eraser', line:'Line', rect:'Rectangle', circle:'Circle', text:'Text'
  };
  const STICKY_PALETTES = [
    { bg:'#FEF9C3', hd:'#FDE68A' },
    { bg:'#DCFCE7', hd:'#BBF7D0' },
    { bg:'#DBEAFE', hd:'#BFDBFE' },
    { bg:'#FCE7F3', hd:'#FBCFE8' },
    { bg:'#FFE4E6', hd:'#FECDD3' },
    { bg:'#F3E8FF', hd:'#E9D5FF' },
  ];
  const PAL_COLORS = [
    '#000000','#1E293B','#64748B','#94A3B8','#CBD5E1','#F1F5F9','#FFFFFF',
    '#EF4444','#F97316','#F59E0B','#EAB308','#84CC16','#22C55E','#10B981',
    '#06B6D4','#3B82F6','#6366F1','#8B5CF6','#A855F7','#EC4899','#F43F5E',
    '#2563EB','#059669','#D97706','#7C3AED','#0F172A','#DC2626','#FBBF24',
  ];

  /* ─────────────────────────────────────────────────────────────────────────
     SCENE STATE
  ───────────────────────────────────────────────────────────────────────── */
  /**
   * Scene objects — stored in world coordinates:
   *  stroke : { id, type:'stroke',    points:[{x,y}], color, width, opacity }
   *  line   : { id, type:'line',      x1,y1,x2,y2,   color, width }
   *  rect   : { id, type:'rect',      x,y,w,h,        color, width }
   *  circle : { id, type:'circle',    cx,cy,rx,ry,    color, width }
   *  text   : { id, type:'text',      x,y,content,    color, fontSize }
   */
  let objects  = [];
  let stickies = [];
  let objSeq   = 1;
  let stickySeq = 1;

  // Camera — single source of truth for viewport
  let cam = { x: 0, y: 0, scale: 1 };

  // Active tool + styling
  let tool      = 'select';
  let color     = '#2563EB';
  let brushSize = 4;

  // Selection
  let selectedId  = null;  // id of selected object or sticky
  let selIsSicky  = false;

  // Interaction state machine
  let iState = 'idle'; // idle | panning | drawing | dragging | resizing
  let panOrigin   = null;  // { mx,my,cx,cy }
  let drawOrigin  = null;  // world coords where stroke/shape started
  let liveStroke  = null;  // stroke being drawn (points[])
  let previewObj  = null;  // shape preview
  let moveOrigin  = null;  // { mx,my,ox,oy } for move-drag
  let resizeHandle= null;  // active resize handle id
  let resizeOrigin= null;  // { mx,my, snapshot of object }
  let spaceHeld   = false;

  // Inline text editing
  let textEditor  = null;  // <textarea> overlay element
  let editingId   = null;  // id of text object being edited

  // History
  let history = [], histIdx = -1;

  // Render scheduling
  let rafPending = false;

  // One-time init flag
  let initialized = false;
  let toastTimer  = null;

  /* ─────────────────────────────────────────────────────────────────────────
     COORDINATE HELPERS
  ───────────────────────────────────────────────────────────────────────── */
  function s2w(sx, sy) {  // screen → world
    return { x: (sx - cam.x) / cam.scale, y: (sy - cam.y) / cam.scale };
  }
  function w2s(wx, wy) {  // world → screen
    return { x: wx * cam.scale + cam.x, y: wy * cam.scale + cam.y };
  }
  function evPos(e) {
    const r = canvasArea.getBoundingClientRect();
    const cl = e.touches ? e.touches[0] : e;
    return { sx: cl.clientX - r.left, sy: cl.clientY - r.top };
  }
  function evWorld(e) {
    const p = evPos(e);
    return s2w(p.sx, p.sy);
  }

  /* ─────────────────────────────────────────────────────────────────────────
     CANVAS SETUP & RESIZE
  ───────────────────────────────────────────────────────────────────────── */
  function resizeCanvas() {
    canvas.width  = canvasArea.clientWidth;
    canvas.height = canvasArea.clientHeight;
    schedRender();
  }

  /* ─────────────────────────────────────────────────────────────────────────
     RENDER LOOP
  ───────────────────────────────────────────────────────────────────────── */
  function schedRender() {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(render);
  }

  function render() {
    rafPending = false;
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Apply camera transform — everything drawn after this is in world space
    ctx.save();
    ctx.translate(cam.x, cam.y);
    ctx.scale(cam.scale, cam.scale);

    // Draw all scene objects
    for (const obj of objects) {
      drawObject(obj, false);
    }

    // Draw live stroke preview
    if (liveStroke && liveStroke.points.length > 1) {
      drawObject(liveStroke, false);
    }
    if (previewObj) {
      drawObject(previewObj, false);
    }

    ctx.restore();

    // Selection + handles drawn in screen space (no scale distortion)
    if (selectedId !== null && !selIsSicky) {
      drawSelectionOverlay();
    }

    // Sync sticky layer transform
    syncStickyLayer();
    updateZoomUI();
  }

  /* ─────────────────────────────────────────────────────────────────────────
     DRAW OBJECT
  ───────────────────────────────────────────────────────────────────────── */
  function drawObject(obj, highlight) {
    ctx.save();
    ctx.globalCompositeOperation = 'source-over';
    switch (obj.type) {
      case 'stroke': drawStroke(obj, highlight); break;
      case 'line':   drawLine(obj, highlight);   break;
      case 'rect':   drawRect(obj, highlight);   break;
      case 'circle': drawCircle(obj, highlight); break;
      case 'text':   drawText(obj, highlight);   break;
    }
    ctx.restore();
  }

  function drawStroke(o, hi) {
    if (!o.points || o.points.length < 2) return;
    ctx.lineCap  = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle  = o.color;
    ctx.lineWidth    = o.width;
    ctx.globalAlpha  = o.opacity || 1;
    ctx.beginPath();
    ctx.moveTo(o.points[0].x, o.points[0].y);
    for (let i = 1; i < o.points.length; i++) ctx.lineTo(o.points[i].x, o.points[i].y);
    ctx.stroke();
    ctx.globalAlpha  = 1;
  }

  function drawLine(o, hi) {
    ctx.lineCap   = 'round';
    ctx.strokeStyle = o.color;
    ctx.lineWidth   = o.width;
    ctx.beginPath();
    ctx.moveTo(o.x1, o.y1);
    ctx.lineTo(o.x2, o.y2);
    ctx.stroke();
  }

  function drawRect(o, hi) {
    ctx.lineCap   = 'round';
    ctx.lineJoin  = 'round';
    ctx.strokeStyle = o.color;
    ctx.lineWidth   = o.width;
    ctx.strokeRect(o.x, o.y, o.w, o.h);
  }

  function drawCircle(o, hi) {
    ctx.lineCap   = 'round';
    ctx.strokeStyle = o.color;
    ctx.lineWidth   = o.width;
    ctx.beginPath();
    ctx.ellipse(o.cx, o.cy, Math.abs(o.rx), Math.abs(o.ry), 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  function drawText(o, hi) {
    ctx.font      = '500 ' + o.fontSize + 'px Inter, sans-serif';
    ctx.fillStyle = o.color;
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
    const lines = (o.content || '').split('\n');
    lines.forEach((line, i) => ctx.fillText(line, o.x, o.y + i * o.fontSize * 1.35));
  }

  /* ─────────────────────────────────────────────────────────────────────────
     SELECTION OVERLAY  (drawn in screen coords, no transform)
  ───────────────────────────────────────────────────────────────────────── */
  function getObjById(id) { return objects.find(o => o.id === id); }

  function getBounds(obj) {
    // Returns world‐space bounding box {x,y,w,h}
    switch (obj.type) {
      case 'stroke': {
        const xs = obj.points.map(p => p.x), ys = obj.points.map(p => p.y);
        const mn = (a) => Math.min(...a), mx = (a) => Math.max(...a);
        return { x:mn(xs)-obj.width/2, y:mn(ys)-obj.width/2, w:mx(xs)-mn(xs)+obj.width, h:mx(ys)-mn(ys)+obj.width };
      }
      case 'line':   return { x:Math.min(obj.x1,obj.x2)-obj.width/2, y:Math.min(obj.y1,obj.y2)-obj.width/2, w:Math.abs(obj.x2-obj.x1)+obj.width, h:Math.abs(obj.y2-obj.y1)+obj.width };
      case 'rect':   return { x:Math.min(obj.x,obj.x+obj.w), y:Math.min(obj.y,obj.y+obj.h), w:Math.abs(obj.w), h:Math.abs(obj.h) };
      case 'circle': return { x:obj.cx-Math.abs(obj.rx), y:obj.cy-Math.abs(obj.ry), w:Math.abs(obj.rx)*2, h:Math.abs(obj.ry)*2 };
      case 'text':   {
        ctx.font = '500 ' + obj.fontSize + 'px Inter, sans-serif';
        const lines = (obj.content||'').split('\n');
        const mw = Math.max(...lines.map(l => ctx.measureText(l).width));
        return { x:obj.x, y:obj.y - obj.fontSize, w: mw || 80, h: lines.length * obj.fontSize * 1.35 };
      }
      default: return { x:0,y:0,w:0,h:0 };
    }
  }

  // Returns 8 handle descriptors [{ id, wx, wy }] in world coords
  function getHandles(obj) {
    const b = getBounds(obj);
    const cx = b.x + b.w/2, cy = b.y + b.h/2;
    return [
      { id:'nw', wx:b.x,      wy:b.y      },
      { id:'n',  wx:cx,       wy:b.y      },
      { id:'ne', wx:b.x+b.w,  wy:b.y      },
      { id:'e',  wx:b.x+b.w,  wy:cy       },
      { id:'se', wx:b.x+b.w,  wy:b.y+b.h  },
      { id:'s',  wx:cx,       wy:b.y+b.h  },
      { id:'sw', wx:b.x,      wy:b.y+b.h  },
      { id:'w',  wx:b.x,      wy:cy       },
    ];
  }

  // Cursor for resize handle
  function handleCursor(id) {
    return { nw:'nw-resize', ne:'ne-resize', sw:'sw-resize', se:'se-resize',
             n:'n-resize', s:'s-resize', e:'e-resize', w:'w-resize' }[id] || 'crosshair';
  }

  function drawSelectionOverlay() {
    const obj = getObjById(selectedId);
    if (!obj) return;
    const b = getBounds(obj);
    // bounding rect in screen coords
    const tl = w2s(b.x,      b.y);
    const br = w2s(b.x+b.w,  b.y+b.h);
    const sw = br.x - tl.x, sh = br.y - tl.y;

    ctx.save();
    // Selection outline
    ctx.strokeStyle = '#2563EB';
    ctx.lineWidth   = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.strokeRect(tl.x - 1, tl.y - 1, sw + 2, sh + 2);
    ctx.setLineDash([]);

    // Handles
    getHandles(obj).forEach(h => {
      const sp = w2s(h.wx, h.wy);
      ctx.fillStyle   = '#fff';
      ctx.strokeStyle = '#2563EB';
      ctx.lineWidth   = 1.5;
      ctx.beginPath();
      ctx.arc(sp.x, sp.y, HANDLE_R, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });
    ctx.restore();
  }

  // Returns handle id if (sx,sy) is within a handle, else null
  function hitHandle(sx, sy, obj) {
    for (const h of getHandles(obj)) {
      const sp = w2s(h.wx, h.wy);
      if (Math.hypot(sx - sp.x, sy - sp.y) <= HANDLE_R + 3) return h.id;
    }
    return null;
  }

  /* ─────────────────────────────────────────────────────────────────────────
     HIT TESTING
  ───────────────────────────────────────────────────────────────────────── */
  function hitTest(wx, wy) {
    // Iterate in reverse (top-most first)
    for (let i = objects.length - 1; i >= 0; i--) {
      if (hitObject(objects[i], wx, wy)) return objects[i].id;
    }
    return null;
  }

  function hitObject(obj, wx, wy) {
    const t = HIT_THRESH / cam.scale;  // hit threshold in world coords
    switch (obj.type) {
      case 'stroke': {
        const pts = obj.points;
        for (let i = 1; i < pts.length; i++) {
          if (distPtSeg(wx, wy, pts[i-1].x, pts[i-1].y, pts[i].x, pts[i].y) < t + obj.width/2) return true;
        }
        return false;
      }
      case 'line':   return distPtSeg(wx, wy, obj.x1, obj.y1, obj.x2, obj.y2) < t + obj.width/2;
      case 'rect':   { const b = getBounds(obj); return wx>=b.x-t && wx<=b.x+b.w+t && wy>=b.y-t && wy<=b.y+b.h+t; }
      case 'circle': { const dx=(wx-obj.cx)/Math.abs(obj.rx||1), dy=(wy-obj.cy)/Math.abs(obj.ry||1); const d=Math.sqrt(dx*dx+dy*dy); return Math.abs(d-1) < t/Math.max(Math.abs(obj.rx||1),1); }
      case 'text':   { const b = getBounds(obj); return wx>=b.x-t && wx<=b.x+b.w+t && wy>=b.y-t && wy<=b.y+b.h+t; }
      default: return false;
    }
  }

  function distPtSeg(px, py, ax, ay, bx, by) {
    const dx = bx-ax, dy = by-ay;
    const len2 = dx*dx + dy*dy;
    if (len2 === 0) return Math.hypot(px-ax, py-ay);
    const t = Math.max(0, Math.min(1, ((px-ax)*dx + (py-ay)*dy) / len2));
    return Math.hypot(px - (ax + t*dx), py - (ay + t*dy));
  }

  /* ─────────────────────────────────────────────────────────────────────────
     OBJECT MUTATION (for resize)
  ───────────────────────────────────────────────────────────────────────── */
  function applyResize(obj, handleId, dwx, dwy) {
    switch (obj.type) {
      case 'line': {
        if (handleId === 'nw' || handleId === 'w' || handleId === 'sw') { obj.x1 += dwx; obj.y1 += dwy; }
        else { obj.x2 += dwx; obj.y2 += dwy; }
        break;
      }
      case 'rect': {
        const b0 = { x:obj.x, y:obj.y, w:obj.w, h:obj.h };
        if (handleId.includes('n')) { obj.y = b0.y + dwy; obj.h = b0.h - dwy; }
        if (handleId.includes('s')) { obj.h = b0.h + dwy; }
        if (handleId.includes('w')) { obj.x = b0.x + dwx; obj.w = b0.w - dwx; }
        if (handleId.includes('e')) { obj.w = b0.w + dwx; }
        break;
      }
      case 'circle': {
        if (handleId.includes('e') || handleId.includes('w')) obj.rx += (handleId.includes('e') ? dwx : -dwx) / 2;
        if (handleId.includes('n') || handleId.includes('s')) obj.ry += (handleId.includes('s') ? dwy : -dwy) / 2;
        break;
      }
      default: break; // strokes / text: no resize
    }
  }

  function moveObject(obj, dwx, dwy) {
    switch (obj.type) {
      case 'stroke': obj.points = obj.points.map(p => ({ x: p.x+dwx, y: p.y+dwy })); break;
      case 'line':   obj.x1+=dwx; obj.y1+=dwy; obj.x2+=dwx; obj.y2+=dwy; break;
      case 'rect':   obj.x+=dwx; obj.y+=dwy; break;
      case 'circle': obj.cx+=dwx; obj.cy+=dwy; break;
      case 'text':   obj.x+=dwx; obj.y+=dwy; break;
    }
  }

  /* ─────────────────────────────────────────────────────────────────────────
     POINTER EVENTS  — Mouse & Touch
  ───────────────────────────────────────────────────────────────────────── */
  canvasArea.addEventListener('mousedown',   onDown);
  canvasArea.addEventListener('mousemove',   onMove);
  canvasArea.addEventListener('mouseup',     onUp);
  canvasArea.addEventListener('mouseleave',  onLeave);
  canvasArea.addEventListener('dblclick',    onDblClick);
  canvasArea.addEventListener('wheel',       onWheel, { passive: false });
  canvasArea.addEventListener('contextmenu', e => e.preventDefault());  // allow RMB panning
  canvasArea.addEventListener('touchstart',  onTouchStart, { passive: false });
  canvasArea.addEventListener('touchmove',   onTouchMove,  { passive: false });
  canvasArea.addEventListener('touchend',    onTouchEnd,   { passive: false });

  let lastTouchDist = 0;

  function onTouchStart(e) {
    e.preventDefault();
    if (e.touches.length === 2) {
      lastTouchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      return;
    }
    onDown(e.touches[0]);
  }
  function onTouchMove(e) {
    e.preventDefault();
    if (e.touches.length === 2) {
      const d = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const r  = canvasArea.getBoundingClientRect();
      const mx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - r.left;
      const my = (e.touches[0].clientY + e.touches[1].clientY) / 2 - r.top;
      applyZoom(d / lastTouchDist, mx, my);
      lastTouchDist = d;
      return;
    }
    onMove(e.touches[0]);
  }
  function onTouchEnd(e) { e.preventDefault(); onUp(e); }

  function onDown(e) {
    if (textEditor) { commitTextEdit(); return; }
    const { sx, sy } = evPos(e);
    const wPos = s2w(sx, sy);

    // ── PAN  (Space held, middle button, or right mouse button) ────────────
    const wantsPin = spaceHeld || e.button === 1 || e.button === 2 || tool === 'pan';
    if (wantsPin) {
      iState = 'panning';
      panOrigin = { mx: sx, my: sy, cx: cam.x, cy: cam.y };
      setCursor('grabbing');
      return;
    }

    // ── SELECT tool ────────────────────────────────────────────────────────
    if (tool === 'select') {
      // Check resize handle first
      if (selectedId !== null && !selIsSicky) {
        const obj = getObjById(selectedId);
        if (obj) {
          const h = hitHandle(sx, sy, obj);
          if (h) {
            iState = 'resizing';
            resizeHandle  = h;
            resizeOrigin  = { mx:sx, my:sy, snapshotJSON: JSON.stringify(obj) };
            setCursor(handleCursor(h));
            return;
          }
        }
      }
      // Check object hit
      const hitId = hitTest(wPos.x, wPos.y);
      if (hitId !== null) {
        selectedId = hitId;
        selIsSicky = false;
        const obj = getObjById(hitId);
        const b = getBounds(obj);
        iState = 'dragging';
        moveOrigin = { mx: sx, my: sy, owx: wPos.x - b.x, owy: wPos.y - b.y };
        setCursor('move');
      } else {
        selectedId = null;
        iState = 'idle';
        setCursor('default');
      }
      schedRender();
      return;
    }

    // ── ERASER ─────────────────────────────────────────────────────────────
    if (tool === 'eraser') {
      eraseAt(wPos.x, wPos.y);
      iState = 'drawing';  // reuse to keep erasing on move
      return;
    }

    // ── PEN / HIGHLIGHTER ──────────────────────────────────────────────────
    if (tool === 'pen' || tool === 'highlighter') {
      iState = 'drawing';
      liveStroke = {
        id: null, type: 'stroke',
        points: [{ x: wPos.x, y: wPos.y }],
        color, width: brushSize, opacity: tool === 'highlighter' ? 0.42 : 1
      };
      return;
    }

    // ── SHAPES + LINE ──────────────────────────────────────────────────────
    if (['line','rect','circle'].includes(tool)) {
      iState = 'drawing';
      drawOrigin = { wx: wPos.x, wy: wPos.y };
      previewObj = makeShape(tool, wPos.x, wPos.y, wPos.x, wPos.y);
      return;
    }

    // ── TEXT ───────────────────────────────────────────────────────────────
    if (tool === 'text') {
      // Prevent browser from stealing focus away from the about-to-be-created
      // textarea (which would cause an immediate blur → silent discard).
      e.preventDefault();
      openTextEditor(null, sx, sy, wPos.x, wPos.y);
      return;
    }
  }

  function onMove(e) {
    const { sx, sy } = evPos(e);
    const wPos = s2w(sx, sy);

    if (iState === 'panning') {
      cam.x = panOrigin.cx + (sx - panOrigin.mx);
      cam.y = panOrigin.cy + (sy - panOrigin.my);
      syncGridBg();
      schedRender();
      return;
    }

    if (iState === 'drawing') {
      if (tool === 'eraser') { eraseAt(wPos.x, wPos.y); return; }
      if (liveStroke) {
        liveStroke.points.push({ x: wPos.x, y: wPos.y });
        schedRender();
      }
      if (previewObj && drawOrigin) {
        previewObj = makeShape(tool, drawOrigin.wx, drawOrigin.wy, wPos.x, wPos.y);
        schedRender();
      }
      return;
    }

    if (iState === 'dragging') {
      const obj = getObjById(selectedId);
      if (!obj) return;
      const b  = getBounds(obj);
      const nwx = wPos.x - moveOrigin.owx;
      const nwy = wPos.y - moveOrigin.owy;
      moveObject(obj, nwx - b.x, nwy - b.y);
      schedRender();
      return;
    }

    if (iState === 'resizing') {
      const obj = getObjById(selectedId);
      if (!obj) return;
      const dwx = (sx - resizeOrigin.mx) / cam.scale;
      const dwy = (sy - resizeOrigin.my) / cam.scale;
      // Restore + re-apply delta fresh each move
      const snap = JSON.parse(resizeOrigin.snapshotJSON);
      Object.assign(obj, snap);
      applyResize(obj, resizeHandle, dwx, dwy);
      schedRender();
      return;
    }

    // Hover cursor update for select tool
    if (tool === 'select') {
      if (selectedId !== null && !selIsSicky) {
        const obj = getObjById(selectedId);
        if (obj) {
          const h = hitHandle(sx, sy, obj);
          if (h) { setCursor(handleCursor(h)); return; }
        }
      }
      const hitId = hitTest(wPos.x, wPos.y);
      setCursor(hitId !== null ? 'move' : 'default');
    }
  }

  function onUp(e) {
    if (iState === 'panning') {
      iState = 'idle';
      setCursor(spaceHeld ? 'grab' : toolCursor());
      return;
    }
    if (iState === 'drawing') {
      if (liveStroke && liveStroke.points.length >= 2) {
        liveStroke.id = objSeq++;
        objects.push(liveStroke);
        pushHistory(); saveToStorage();
      }
      liveStroke = null;
      if (previewObj && drawOrigin) {
        const wp  = evWorld(e);
        const fin = makeShape(tool, drawOrigin.wx, drawOrigin.wy, wp.x, wp.y);
        fin.id = objSeq++;
        objects.push(fin);
        selectedId = fin.id; selIsSicky = false;
        previewObj = null; drawOrigin = null;
        pushHistory(); saveToStorage();
        // Switch to select so the user can immediately drag the resize handles.
        setTool('select');
      }
    }
    if (iState === 'dragging' || iState === 'resizing') {
      pushHistory(); saveToStorage();
    }
    iState = 'idle';
    setCursor(toolCursor());
    schedRender();
  }

  function onLeave(e) { if (iState !== 'idle') onUp(e); }

  /* ─────────────────────────────────────────────────────────────────────────
     DOUBLE CLICK — text edit
  ───────────────────────────────────────────────────────────────────────── */
  function onDblClick(e) {
    const { sx, sy } = evPos(e);
    const wPos = s2w(sx, sy);
    const hitId = hitTest(wPos.x, wPos.y);
    if (hitId !== null) {
      const obj = getObjById(hitId);
      if (obj && obj.type === 'text') {
        openTextEditor(obj, sx, sy, obj.x, obj.y);
      }
    } else if (tool === 'text') {
      openTextEditor(null, sx, sy, wPos.x, wPos.y);
    }
  }

  /* ─────────────────────────────────────────────────────────────────────────
     ZOOM
  ───────────────────────────────────────────────────────────────────────── */
  function onWheel(e) {
    e.preventDefault();
    const r  = canvasArea.getBoundingClientRect();
    const sx = e.clientX - r.left, sy = e.clientY - r.top;
    applyZoom(e.deltaY < 0 ? 1.1 : 0.909, sx, sy);
  }

  function applyZoom(factor, sx, sy) {
    const ns = Math.max(0.05, Math.min(20, cam.scale * factor));
    const f  = ns / cam.scale;
    cam.x = sx - (sx - cam.x) * f;
    cam.y = sy - (sy - cam.y) * f;
    cam.scale = ns;
    syncGridBg();
    schedRender();
  }

  /* ─────────────────────────────────────────────────────────────────────────
     ERASER
  ───────────────────────────────────────────────────────────────────────── */
  function eraseAt(wx, wy) {
    const t = (brushSize * 3) / cam.scale;
    const before = objects.length;
    objects = objects.filter(o => !hitObjectRadius(o, wx, wy, t));
    if (objects.length !== before) {
      if (selectedId !== null && !getObjById(selectedId)) selectedId = null;
      schedRender(); saveToStorage();
    }
  }

  function hitObjectRadius(obj, wx, wy, r) {
    const b = getBounds(obj);
    const cx = b.x + b.w/2, cy = b.y + b.h/2;
    return Math.hypot(wx - cx, wy - cy) < r + Math.max(b.w, b.h) / 2;
  }

  /* ─────────────────────────────────────────────────────────────────────────
     SHAPE FACTORY
  ───────────────────────────────────────────────────────────────────────── */
  function makeShape(t, x1, y1, x2, y2) {
    const base = { id: null, color, width: brushSize };
    if (t === 'line')   return { ...base, type:'line', x1, y1, x2, y2 };
    if (t === 'rect')   return { ...base, type:'rect', x:x1, y:y1, w:x2-x1, h:y2-y1 };
    if (t === 'circle') return { ...base, type:'circle', cx:(x1+x2)/2, cy:(y1+y2)/2, rx:Math.abs(x2-x1)/2, ry:Math.abs(y2-y1)/2 };
  }

  /* ─────────────────────────────────────────────────────────────────────────
     INLINE TEXT EDITOR
  ───────────────────────────────────────────────────────────────────────── */
  function openTextEditor(existingObj, sx, sy, wx, wy) {
    cancelTextEdit();
    editingId = existingObj ? existingObj.id : null;

    const fsize = Math.max(13, brushSize * 4);
    const r     = canvasArea.getBoundingClientRect();

    // Position textarea at screen coords of the world point
    const sp = existingObj ? w2s(existingObj.x, existingObj.y - existingObj.fontSize) : { x: sx, y: sy };

    textEditor = document.createElement('textarea');
    textEditor.value = existingObj ? existingObj.content : '';
    Object.assign(textEditor.style, {
      position:   'fixed',
      left:       (r.left + sp.x) + 'px',
      top:        (r.top  + sp.y) + 'px',
      minWidth:   '180px',
      minHeight:  '48px',
      fontSize:   Math.round(fsize * cam.scale) + 'px',
      fontFamily: 'Inter, sans-serif',
      fontWeight: '500',
      color:      color,
      background: 'var(--surface)',
      border:     '2px solid var(--clr-primary, #2563EB)',
      borderRadius: '10px',
      padding:    '8px 12px',
      resize:     'both',
      zIndex:     '99998',
      outline:    'none',
      boxShadow:  '0 4px 20px rgba(37,99,235,.25)',
      lineHeight: '1.45',
    });
    textEditor.placeholder = 'Type… Enter = new line, Shift+Enter = place, Esc = cancel';
    textEditor.__wx = wx; textEditor.__wy = wy;

    document.body.appendChild(textEditor);
    textEditor.focus();
    textEditor.select();

    textEditor.addEventListener('keydown', ke => {
      if (ke.key === 'Escape')                      { cancelTextEdit(); }
      if (ke.key === 'Enter' && ke.shiftKey)        { ke.preventDefault(); commitTextEdit(); }
    });
    textEditor.addEventListener('blur', () => setTimeout(commitTextEdit, 80));
  }

  function commitTextEdit() {
    if (!textEditor) return;
    const val = textEditor.value.trim();
    const wx  = textEditor.__wx;
    const wy  = textEditor.__wy;
    const fsize = Math.max(13, brushSize * 4);
    const te  = textEditor;
    textEditor = null;
    te.remove();

    if (!val) { editingId = null; return; }

    if (editingId !== null) {
      const obj = getObjById(editingId);
      if (obj) { obj.content = val; obj.color = color; }
    } else {
      objects.push({ id: objSeq++, type:'text', x:wx, y:wy, content:val, color, fontSize:fsize });
    }
    editingId = null;
    pushHistory(); saveToStorage(); schedRender();
  }

  function cancelTextEdit() {
    if (!textEditor) return;
    const te = textEditor;
    textEditor = null;
    editingId  = null;
    te.remove();
  }

  /* ─────────────────────────────────────────────────────────────────────────
     TOOL BAR WIRING
  ───────────────────────────────────────────────────────────────────────── */
  toolBtns.forEach(btn => btn.addEventListener('click', () => setTool(btn.dataset.tool)));

  /* ── FLOATING TOOLTIP ───────────────────────────────────────────────────
     Rendered as a fixed-position div so it's never clipped by the topbar's
     overflow-y: hidden.                                                     */
  const floatTip = document.getElementById('wbFloatTip');
  let tipTimer;
  toolBtns.forEach(btn => {
    btn.addEventListener('mouseenter', () => {
      const label = btn.dataset.tip;
      if (!label) return;
      clearTimeout(tipTimer);
      floatTip.textContent = label;
      const r = btn.getBoundingClientRect();
      // Position centred below the button
      const left = r.left + r.width / 2;
      const top  = r.bottom + 8;
      floatTip.style.left      = left + 'px';
      floatTip.style.top       = top  + 'px';
      floatTip.style.transform = 'translateX(-50%)';
      floatTip.classList.add('visible');
    });
    btn.addEventListener('mouseleave', () => {
      tipTimer = setTimeout(() => floatTip.classList.remove('visible'), 80);
    });
  });

  function setTool(t) {
    cancelTextEdit();
    tool = t;
    toolBtns.forEach(b => b.classList.toggle('active', b.dataset.tool === t));
    setCursor(toolCursor());
    toolNameEl.textContent = TOOL_LABELS[t] || t;
  }

  function toolCursor() {
    if (spaceHeld) return 'grab';
    switch (tool) {
      case 'select':      return 'default';
      case 'eraser':      return 'cell';
      case 'text':        return 'text';
      case 'pen':
      case 'highlighter':
      case 'line':
      case 'rect':
      case 'circle':      return 'crosshair';
      default:            return 'default';
    }
  }

  function setCursor(cur) {
    canvasArea.style.cursor = cur;
  }

  /* ─────────────────────────────────────────────────────────────────────────
     COLOUR PALETTE
  ───────────────────────────────────────────────────────────────────────── */
  function buildPalette() {
    paletteGrid.innerHTML = '';
    PAL_COLORS.forEach(c => {
      const sw = document.createElement('button');
      sw.className = 'wb-pal-swatch';
      sw.style.background = c;
      sw.addEventListener('click', () => { setColor(c); paletteEl.classList.remove('open'); });
      paletteGrid.appendChild(sw);
    });
  }

  function setColor(c) {
    color = c;
    colorSwatch.style.background = c;
    customColorEl.value = c;
    // Update selected object colour
    if (selectedId !== null) {
      const obj = getObjById(selectedId);
      if (obj) {
        if ('color' in obj) obj.color = c;
        pushHistory(); saveToStorage(); schedRender();
      }
    }
  }

  colorSwatch.addEventListener('click', e => {
    e.stopPropagation();
    const rect = colorSwatch.getBoundingClientRect();
    paletteEl.style.top  = (rect.bottom + 8) + 'px';
    paletteEl.style.left = rect.left + 'px';
    paletteEl.classList.toggle('open');
  });

  document.addEventListener('click', e => {
    if (!paletteEl.contains(e.target) && e.target !== colorSwatch)
      paletteEl.classList.remove('open');
  });
  customColorEl.addEventListener('input', () => setColor(customColorEl.value));

  /* ─────────────────────────────────────────────────────────────────────────
     SIZE SLIDER
  ───────────────────────────────────────────────────────────────────────── */
  sizeSlider.addEventListener('input', () => {
    brushSize = parseInt(sizeSlider.value, 10);
    sizeVal.textContent = brushSize;
    // Apply to selected object
    if (selectedId !== null) {
      const obj = getObjById(selectedId);
      if (obj && 'width' in obj) {
        obj.width = brushSize;
        pushHistory(); saveToStorage(); schedRender();
      }
    }
  });

  /* ─────────────────────────────────────────────────────────────────────────
     GRID BACKGROUND SYNC
  ───────────────────────────────────────────────────────────────────────── */
  function syncGridBg() {
    const gs = 40 * cam.scale;
    canvasArea.style.backgroundSize     = gs + 'px ' + gs + 'px';
    canvasArea.style.backgroundPosition = (cam.x % gs) + 'px ' + (cam.y % gs) + 'px';
  }

  function syncStickyLayer() {
    stickyLayer.style.transform = `matrix(${cam.scale},0,0,${cam.scale},${cam.x},${cam.y})`;
  }

  /* ─────────────────────────────────────────────────────────────────────────
     OPEN / CLOSE
  ───────────────────────────────────────────────────────────────────────── */
  openBtn.addEventListener('click', openWB);
  closeBtn.addEventListener('click', closeWB);

  function openWB() {
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    setTimeout(() => {
      if (!initialized) {
        initialized = true;
        resizeCanvas();
        buildPalette();
        setTool('select');
        loadFromStorage();
        if (history.length === 0) pushHistory();
        syncGridBg();
        syncStickyLayer();
      } else {
        resizeCanvas();
        syncGridBg();
        syncStickyLayer();
        schedRender();
      }
    }, 40);
  }

  function closeWB() {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
    cancelTextEdit();
  }

  window.addEventListener('resize', () => {
    if (overlay.classList.contains('open')) resizeCanvas();
  });

  /* ─────────────────────────────────────────────────────────────────────────
     UNDO / REDO
  ───────────────────────────────────────────────────────────────────────── */
  undoBtn.addEventListener('click', undo);
  redoBtn.addEventListener('click', redo);

  function pushHistory() {
    history = history.slice(0, histIdx + 1);
    history.push({
      objects:  deepClone(objects),
      stickies: deepClone(stickies),
      cam: { ...cam },
    });
    if (history.length > MAX_HIST) history.shift();
    histIdx = history.length - 1;
    updateUndoRedo();
  }

  function applySnapshot(snap) {
    objects  = deepClone(snap.objects);
    stickies = deepClone(snap.stickies);
    cam      = { ...snap.cam };
    selectedId = null;
    renderAllStickies();
    syncGridBg();
    schedRender();
    updateUI();
  }

  function undo() { if (histIdx > 0)  applySnapshot(history[--histIdx]); updateUndoRedo(); }
  function redo() { if (histIdx < history.length-1) applySnapshot(history[++histIdx]); updateUndoRedo(); }

  /* ─────────────────────────────────────────────────────────────────────────
     CLEAR
  ───────────────────────────────────────────────────────────────────────── */
  clearBtn.addEventListener('click', () => {
    if (!confirm('Clear the entire board? All drawings and notes will be removed.')) return;
    objects  = []; stickies = [];
    selectedId = null;
    cam = { x:0, y:0, scale:1 };
    stickyLayer.innerHTML = '';
    syncGridBg(); schedRender(); pushHistory(); saveToStorage(); updateUI();
    showToast('Board cleared');
  });

  /* ─────────────────────────────────────────────────────────────────────────
     DELETE SELECTED
  ───────────────────────────────────────────────────────────────────────── */
  function deleteSelected() {
    if (selectedId === null) return;
    if (selIsSicky) {
      deleteSticky(selectedId);
    } else {
      objects = objects.filter(o => o.id !== selectedId);
      selectedId = null;
      pushHistory(); saveToStorage(); schedRender();
    }
  }

  /* ─────────────────────────────────────────────────────────────────────────
     SAVE / LOAD (localStorage)
  ───────────────────────────────────────────────────────────────────────── */
  saveBtn.addEventListener('click', () => { saveToStorage(); showToast('Saved to browser ✓'); });

  function saveToStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ objects, stickies, cam, color, brushSize, tool }));
    } catch (_) { /* quota */ }
  }

  function loadFromStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const d = JSON.parse(raw);
      if (d.objects)  objects  = d.objects;
      if (d.stickies) stickies = d.stickies;
      if (d.cam)      Object.assign(cam, d.cam);
      if (d.color)    setColor(d.color);
      if (d.brushSize){ brushSize = d.brushSize; sizeSlider.value = brushSize; sizeVal.textContent = brushSize; }
      if (d.tool)     setTool(d.tool);
      if (stickies.length) {
        stickySeq = Math.max(...stickies.map(s => s.id), 0) + 1;
        renderAllStickies();
      }
      if (objects.length) objSeq = Math.max(...objects.map(o => o.id), 0) + 1;
      pushHistory();
    } catch (_) { /* ignore */ }
  }

  /* ─────────────────────────────────────────────────────────────────────────
     EXPORT PNG
  ───────────────────────────────────────────────────────────────────────── */
  exportBtn.addEventListener('click', exportPNG);

  function exportPNG() {
    const W = canvasArea.clientWidth, H = canvasArea.clientHeight;
    const off = document.createElement('canvas');
    off.width = W; off.height = H;
    const oc  = off.getContext('2d');
    const dk  = document.documentElement.getAttribute('data-theme') === 'dark';

    oc.fillStyle = dk ? '#0B1120' : '#F0F4F8';
    oc.fillRect(0, 0, W, H);

    // Grid
    const gs = 40 * cam.scale, ox = cam.x % gs, oy = cam.y % gs;
    oc.strokeStyle = dk ? 'rgba(148,163,184,.07)' : 'rgba(100,116,139,.1)';
    oc.lineWidth = 1;
    for (let x = ox; x < W; x += gs) { oc.beginPath(); oc.moveTo(x,0); oc.lineTo(x,H); oc.stroke(); }
    for (let y = oy; y < H; y += gs) { oc.beginPath(); oc.moveTo(0,y); oc.lineTo(W,y); oc.stroke(); }

    // Canvas content
    oc.drawImage(canvas, 0, 0, W, H);

    // Stickies
    stickies.forEach(s => {
      const sx = s.x * cam.scale + cam.x, sy = s.y * cam.scale + cam.y;
      const sw = s.w * cam.scale, sh = s.h * cam.scale;
      const pal = STICKY_PALETTES[s.colorIdx % STICKY_PALETTES.length];
      oc.fillStyle = pal.bg;
      roundRect(oc, sx, sy, sw, sh, 12); oc.fill();
      oc.fillStyle = pal.hd;
      roundRect(oc, sx, sy, sw, Math.min(28 * cam.scale, sh * .3), 12); oc.fill();
      const fs = Math.max(9, 13 * cam.scale);
      oc.font = `normal ${fs}px Inter, sans-serif`;
      oc.fillStyle = 'rgba(0,0,0,.72)';
      (s.text||'').split('\n').forEach((ln, i) =>
        oc.fillText(ln, sx + 10*cam.scale, sy + 36*cam.scale + i*fs*1.4, sw - 18*cam.scale));
    });

    const a = document.createElement('a');
    a.download = 'whiteboard-san.png';
    a.href = off.toDataURL('image/png');
    a.click();
    showToast('PNG exported ↓');
  }

  function roundRect(c, x, y, w, h, r) {
    c.beginPath(); c.roundRect(x, y, w, h, r);
  }

  /* ─────────────────────────────────────────────────────────────────────────
     STICKY NOTES
  ───────────────────────────────────────────────────────────────────────── */
  addStickyBtn.addEventListener('click', () => {
    const wp = s2w(canvasArea.clientWidth / 2, canvasArea.clientHeight / 2);
    addSticky(wp.x - 95, wp.y - 70, 0);
  });

  function addSticky(wx, wy, colorIdx) {
    const s = { id: stickySeq++, x:wx, y:wy, w:190, h:150, text:'', colorIdx, zIdx: stickySeq };
    stickies.push(s);
    createStickyEl(s);
    pushHistory(); saveToStorage(); updateUI();
  }

  function renderAllStickies() {
    stickyLayer.innerHTML = '';
    stickies.forEach(s => createStickyEl(s));
    updateUI();
  }

  function createStickyEl(s) {
    const pal = STICKY_PALETTES[s.colorIdx % STICKY_PALETTES.length];
    const el  = document.createElement('div');
    el.className  = 'sticky-note';
    el.dataset.id = s.id;
    el.style.cssText = `left:${s.x}px;top:${s.y}px;width:${s.w}px;height:${s.h}px;background:${pal.bg};z-index:${s.zIdx};`;

    const hd = document.createElement('div');
    hd.className = 'sticky-header';
    hd.style.background = pal.hd;

    const dots = document.createElement('div');
    dots.className = 'sticky-color-dots';
    STICKY_PALETTES.forEach((p, i) => {
      const d = document.createElement('button');
      d.className = 'sticky-color-dot';
      d.style.background = p.hd;
      if (i === s.colorIdx) d.style.outline = '2px solid rgba(0,0,0,.4)';
      d.addEventListener('click', ev => { ev.stopPropagation(); changeStickyColor(s.id, i); });
      dots.appendChild(d);
    });

    const del = document.createElement('button');
    del.className = 'sticky-del-btn';
    del.innerHTML = '&times;';
    del.addEventListener('click', ev => { ev.stopPropagation(); deleteSticky(s.id); });

    hd.appendChild(dots); hd.appendChild(del);

    const ta = document.createElement('textarea');
    ta.className   = 'sticky-text';
    ta.placeholder = 'Type a note…';
    ta.value       = s.text || '';
    ta.addEventListener('input', () => { s.text = ta.value; saveToStorage(); });
    ta.addEventListener('mousedown', ev => ev.stopPropagation());
    ta.addEventListener('touchstart', ev => ev.stopPropagation(), { passive: true });

    const rh = document.createElement('div');
    rh.className = 'sticky-resize';
    rh.addEventListener('mousedown', ev => { ev.stopPropagation(); startStickyResize(ev, s, el); });

    el.appendChild(hd); el.appendChild(ta); el.appendChild(rh);
    stickyLayer.appendChild(el);

    hd.addEventListener('mousedown', ev => { ev.stopPropagation(); startStickyDrag(ev, s, el); });
    hd.addEventListener('touchstart', ev => { ev.stopPropagation(); startStickyDrag(ev.touches[0], s, el); }, { passive: false });

    el.addEventListener('mousedown', ev => {
      selectedId = s.id; selIsSicky = true;
    });
  }

  function startStickyDrag(e, s, el) {
    const aR = canvasArea.getBoundingClientRect();
    const offX = (e.clientX - aR.left) / cam.scale - cam.x / cam.scale - s.x;
    const offY = (e.clientY - aR.top)  / cam.scale - cam.y / cam.scale - s.y;
    s.zIdx = stickySeq++; el.style.zIndex = s.zIdx;

    function move(me) {
      const x = (me.clientX - aR.left) / cam.scale - cam.x / cam.scale - offX;
      const y = (me.clientY - aR.top)  / cam.scale - cam.y / cam.scale - offY;
      s.x = x; s.y = y;
      el.style.left = x + 'px'; el.style.top = y + 'px';
    }
    function up() {
      document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
      document.removeEventListener('touchmove', tmove); document.removeEventListener('touchend', up);
      pushHistory(); saveToStorage();
    }
    function tmove(te) { move(te.touches[0]); }
    document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
    document.addEventListener('touchmove', tmove); document.addEventListener('touchend', up);
  }

  function startStickyResize(e, s, el) {
    const s0w = s.w, s0h = s.h, m0x = e.clientX, m0y = e.clientY;
    function move(me) {
      s.w = Math.max(150, s0w + (me.clientX - m0x) / cam.scale);
      s.h = Math.max(110, s0h + (me.clientY - m0y) / cam.scale);
      el.style.width  = s.w + 'px';
      el.style.height = s.h + 'px';
    }
    function up() {
      document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
      pushHistory(); saveToStorage();
    }
    document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
  }

  function changeStickyColor(id, colorIdx) {
    const s = stickies.find(n => n.id === id); if (!s) return;
    s.colorIdx = colorIdx;
    const el = stickyLayer.querySelector(`[data-id="${id}"]`);
    if (el) el.remove();
    createStickyEl(s);
    pushHistory(); saveToStorage();
  }

  function deleteSticky(id) {
    stickies = stickies.filter(s => s.id !== id);
    const el = stickyLayer.querySelector(`[data-id="${id}"]`);
    if (el) el.remove();
    if (selectedId === id) selectedId = null;
    pushHistory(); saveToStorage(); updateUI();
  }

  /* ─────────────────────────────────────────────────────────────────────────
     KEYBOARD SHORTCUTS
  ───────────────────────────────────────────────────────────────────────── */
  document.addEventListener('keydown', e => {
    if (!overlay.classList.contains('open')) return;
    const tag = document.activeElement.tagName;
    if (tag === 'TEXTAREA' || tag === 'INPUT') return;

    if (e.code === 'Space')  { e.preventDefault(); spaceHeld = true;  setCursor('grab'); return; }
    if (e.key  === 'Escape') { closeWB(); return; }

    if (e.ctrlKey || e.metaKey) {
      if   (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
      else if (e.key === 'z' || e.key === 'y') { e.preventDefault(); redo(); }
      else if (e.key === 's') { e.preventDefault(); saveToStorage(); showToast('Saved ✓'); }
      else if (e.key === 'e') { e.preventDefault(); exportPNG(); }
      return;
    }

    const tmap = { v:'select', p:'pen', h:'highlighter', e:'eraser', l:'line', r:'rect', c:'circle', t:'text' };
    if (tmap[e.key.toLowerCase()]) { setTool(tmap[e.key.toLowerCase()]); return; }
    if (e.key.toLowerCase() === 'n') { addStickyBtn.click(); return; }

    if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
    if (e.key === '0' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      cam = { x:0, y:0, scale:1 }; syncGridBg(); schedRender();
    }
  });

  document.addEventListener('keyup', e => {
    if (e.code === 'Space') { spaceHeld = false; setCursor(toolCursor()); }
  });

  /* ─────────────────────────────────────────────────────────────────────────
     UI HELPERS
  ───────────────────────────────────────────────────────────────────────── */
  function updateZoomUI() {
    zoomPctEl.textContent = Math.round(cam.scale * 100) + '%';
  }
  function updateUndoRedo() {
    undoBtn.disabled = histIdx <= 0;
    redoBtn.disabled = histIdx >= history.length - 1;
  }
  function updateUI() {
    itemCountEl.textContent = stickies.length;
    toolNameEl.textContent  = TOOL_LABELS[tool] || tool;
    updateUndoRedo();
  }

  let toastTm;
  function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    clearTimeout(toastTm);
    toastTm = setTimeout(() => toastEl.classList.remove('show'), 2400);
  }

  function deepClone(o) { return JSON.parse(JSON.stringify(o)); }

})();