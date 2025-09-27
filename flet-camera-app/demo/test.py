import matching as mt
import cv2
import os
import math
import numpy as np

# Example paths (update to your images)
template1 = '/home/iiot-b20/Documents/Robotvision/flet-camera-app/image_comppressor_picture/temp1.jpg'
template2 = '/home/iiot-b20/Documents/Robotvision/flet-camera-app/image_comppressor_picture/temp3.png'
source = '/home/iiot-b20/Documents/Robotvision/flet-camera-app/image_comppressor_picture/Image_21.png'

def _resolve_path(p: str) -> str:
    import os
    if os.path.exists(p):
        return p
    # Fix double extensions like .png.jpg or .jpg.png
    if p.endswith('.png.jpg'):
        alt = p[:-4]
        if os.path.exists(alt):
            return alt
    if p.endswith('.jpg.png'):
        alt = p[:-4]
        if os.path.exists(alt):
            return alt
    # Try swapping common extensions
    root, ext = os.path.splitext(p)
    for new_ext in ('.jpg', '.jpeg', '.png'):
        if new_ext.lower() == ext.lower():
            continue
        alt = root + new_ext
        if os.path.exists(alt):
            return alt
    return p

template1 = _resolve_path(template1)
template2 = _resolve_path(template2)
source = _resolve_path(source)

template1_img = cv2.imread(template1)
template2_img = cv2.imread(template2)
if template1_img is None:
    raise SystemExit(f"Failed to read template1 image. Please verify the path: {template1}")
if template2_img is None:
    raise SystemExit(f"Failed to read template2 image. Please verify the path: {template2}")

dll_path = mt.find_library_path()
params1 = mt.MatchingParams(maxCount=1, scoreThreshold=0.6, iouThreshold=0.8, angle=5.0)
params2 = mt.MatchingParams(maxCount=1, scoreThreshold=0.4, iouThreshold=0.6, angle=1.0)
matcher1 = mt.create_matcher_for_template(template1_img, dll_path, params1)
matcher2 = mt.create_matcher_for_template(template2_img, dll_path, params2)

# Prepare an image list to navigate. If `source` is a directory, use it; otherwise use
# the directory containing the provided source file and start at that file.
def _list_images(dir_path: str):
    exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
    items = []
    try:
        for name in sorted(os.listdir(dir_path)):
            _, ext = os.path.splitext(name)
            if ext.lower() in exts:
                items.append(os.path.join(dir_path, name))
    except Exception as e:
        print(f"Failed to list images in {dir_path}: {e}")
    return items

if os.path.isdir(source):
    img_list = _list_images(source)
    start_idx = 0
else:
    src_dir = os.path.dirname(source) or '.'
    img_list = _list_images(src_dir)
    try:
        start_idx = img_list.index(source)
    except ValueError:
        base = os.path.basename(source)
        start_idx = next((i for i, p in enumerate(img_list) if os.path.basename(p) == base), 0)

if not img_list:
    raise SystemExit(f"No images found to browse in: {source}")

win = 'match_view'
cv2.namedWindow(win, cv2.WINDOW_NORMAL)
idx = start_idx

def _first_center(centers):
    if not centers:
        return None
    if isinstance(centers, (tuple, list)) and len(centers) == 2 and all(isinstance(v, (int, float)) for v in centers):
        return (int(centers[0]), int(centers[1]))
    try:
        c = centers[0]
        return (int(c[0]), int(c[1]))
    except Exception:
        return None

def angle_between(p1, p2, p3):
    v = np.array([p2[0] - p1[0], p2[1] - p1[1]], dtype=float)
    u = np.array([p3[0] - p1[0], p3[1] - p1[1]], dtype=float)
    nv = np.linalg.norm(v)
    nu = np.linalg.norm(u)
    if nv == 0 or nu == 0:
        return None
    dot = float(np.dot(v, u))
    det = float(v[0] * u[1] - v[1] * u[0])
    ang = math.degrees(math.atan2(det, dot))
    return ang

while True:
    img_path = img_list[idx]
    src_img = cv2.imread(img_path)
    if src_img is None:
        print(f"Failed to read image: {img_path}")
        idx = (idx + 1) % len(img_list)
        continue

    # run matchers (support both 2- and 3-value run_match signatures)
    try:
        ret1 = mt.run_match(matcher1, src_img)
        if len(ret1) == 3:
            count1, results1, centers1 = ret1
        else:
            count1, results1 = ret1
            centers1 = None
    except Exception as e:
        print(f"matcher1 error: {e}")
        count1, results1, centers1 = 0, [], None

    try:
        ret2 = mt.run_match(matcher2, src_img)
        if len(ret2) == 3:
            count2, results2, centers2 = ret2
        else:
            count2, results2 = ret2
            centers2 = None
    except Exception as e:
        print(f"matcher2 error: {e}")
        count2, results2, centers2 = 0, [], None

    # fallback: if centers not returned, try to derive from results using result_to_points
    if centers1 is None:
        try:
            centers1 = []
            for r in results1:
                pts = mt.result_to_points(r)
                if pts is not None and len(pts):
                    c = tuple(map(int, pts.mean(axis=0)))
                    centers1.append(c)
        except Exception:
            centers1 = []
    if centers2 is None:
        try:
            centers2 = []
            for r in results2:
                pts = mt.result_to_points(r)
                if pts is not None and len(pts):
                    c = tuple(map(int, pts.mean(axis=0)))
                    centers2.append(c)
        except Exception:
            centers2 = []

    print(f"[{idx+1}/{len(img_list)}] {os.path.basename(img_path)} -> matches: t1={count1}, t2={count2}")

    # visualization
    vis = mt.draw_results(src_img.copy(), list(results1) + list(results2))
    c1 = _first_center(centers1)
    c2 = _first_center(centers2)
    c3 = None
    if c1 and c2:
        c3 = (int(c1[0]), int(c2[1]))
        cv2.line(vis, c1, c2, (0, 0, 255), thickness=2, lineType=cv2.LINE_AA)
        cv2.circle(vis, c1, 4, (0, 255, 0), -1, lineType=cv2.LINE_AA)
        cv2.circle(vis, c2, 4, (255, 0, 0), -1, lineType=cv2.LINE_AA)
        cv2.circle(vis, c3, 4, (0, 255, 255), -1, lineType=cv2.LINE_AA)
        cv2.line(vis, c1, c3, (0, 255, 255), thickness=1, lineType=cv2.LINE_AA)
        cv2.line(vis, c3, c2, (0, 255, 255), thickness=1, lineType=cv2.LINE_AA)

        ang_signed = angle_between(c1, c2, c3)
        if ang_signed is None:
            ang_text = "angle: n/a"
        else:
            ang_abs = abs(ang_signed)
            ang_text = f"angle: {ang_abs:.1f} deg (signed {ang_signed:.1f})"
        txt_pos = (int(c1[0] + 8), int(c1[1] - 10))
        cv2.putText(vis, ang_text, txt_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    cv2.imshow(win, cv2.resize(vis, (min(1200, vis.shape[1]), min(800, vis.shape[0]))))

    k = cv2.waitKeyEx(0)
    # q or ESC to quit
    if k in (ord('q'), 27):
        break
    # left arrow
    elif k in (81, 2424832):
        idx = (idx - 1) % len(img_list)
    # right arrow
    elif k in (83, 2555904):
        idx = (idx + 1) % len(img_list)
    # save current visualization
    elif k in (ord('s'), ord('S')):
        out_name = os.path.splitext(os.path.basename(img_path))[0] + '_match.png'
        out_path = os.path.join(os.path.dirname(img_path), out_name)
        cv2.imwrite(out_path, vis)
        print(f"Saved: {out_path}")
    else:
        # any other key: advance
        idx = (idx + 1) % len(img_list)

cv2.destroyAllWindows()
mt.release_matcher(matcher1)
mt.release_matcher(matcher2)