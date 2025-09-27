import matching as mt
import cv2
import os
import math
import numpy as np

# Example paths (update to your images)
template1 = '/home/iiot-b20/Documents/Robotvision/flet-camera-app/image_comppressor_picture/temp.jpg'
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
source_img = cv2.imread(source)
if template1_img is None:
	raise SystemExit(f"Failed to read template1 image. Please verify the path: {template1}")
if template2_img is None:
	raise SystemExit(f"Failed to read template2 image. Please verify the path: {template2}")
if source_img is None:
	raise SystemExit(f"Failed to read source image. Please verify the path: {source}")


dll_path = mt.find_library_path()

def _first_center(centers):
    # centers can be a tuple (x,y) or a list of tuples; return (int(x), int(y)) or None
    if not centers:
        return None
    if isinstance(centers, (tuple, list)) and len(centers) == 2 and all(isinstance(v, (int, float)) for v in centers):
        return (int(centers[0]), int(centers[1]))
    # assume list-like of points
    try:
        c = centers[0]
        return (int(c[0]), int(c[1]))
    except Exception:
        return None

def _angle_between(p1, p2, p3):
    # returns signed angle degrees from vector p1->p2 to p1->p3 (-180..180)
    v = np.array([p2[0] - p1[0], p2[1] - p1[1]], dtype=float)
    u = np.array([p3[0] - p1[0], p3[1] - p1[1]], dtype=float)
    nv = np.linalg.norm(v)
    nu = np.linalg.norm(u)
    if nv == 0 or nu == 0:
        return None
    dot = float(np.dot(v, u))
    det = float(v[0] * u[1] - v[1] * u[0])  # 2D cross (z)
    ang = math.degrees(math.atan2(det, dot))
    return ang

def match_and_annotate(template1_img,
                       template2_img,
                       source_img,
                       dll_path=None,
                       params1=None,
                       params2=None,
                       draw_angle=True):

    if dll_path is None:
        dll_path = mt.find_library_path()

    if params1 is None:
        params1 = mt.MatchingParams(maxCount=1, scoreThreshold=0.6, iouThreshold=0.8, angle=5.0)
    if params2 is None:
        params2 = mt.MatchingParams(maxCount=1, scoreThreshold=0.4, iouThreshold=0.6, angle=1.0)

    matcher1 = mt.create_matcher_for_template(template1_img, dll_path, params1)
    matcher2 = mt.create_matcher_for_template(template2_img, dll_path, params2)

    count1, results1, center1 = mt.run_match(matcher1, source_img)
    count2, results2, center2 = mt.run_match(matcher2, source_img)

    c1 = _first_center(center1)
    c2 = _first_center(center2)
    c3 = None
    if c1 and c2:
        c3 = (int(c1[0]), int(c2[1]))

    # draw combined results
    image = source_img.copy()
    image = mt.draw_results(image, list(results1) + list(results2))

    if c1 and c2:
        cv2.line(image, c1, c2, (0, 0, 255), thickness=1, lineType=cv2.LINE_AA)
        cv2.circle(image, c1, 3, (0, 255, 0), -1, lineType=cv2.LINE_AA)
        cv2.circle(image, c2, 3, (255, 0, 0), -1, lineType=cv2.LINE_AA)

        if draw_angle and c3:
            ang_signed = _angle_between(c1, c2, c3)
            if ang_signed is None:
                ang_text = "angle: n/a"
            else:
                ang_abs = abs(ang_signed)
                ang_text = f"angle: {ang_abs:.1f} deg (signed {ang_signed:.1f})"
            txt_pos = (int(c1[0] + 8), int(c1[1] - 10))
            cv2.putText(image, ang_text, txt_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.circle(image, c3, 3, (0, 255, 255), -1, lineType=cv2.LINE_AA)
            cv2.line(image, c3, c1, (0, 0, 255), thickness=1, lineType=cv2.LINE_AA)
            cv2.line(image, c3, c2, (0, 0, 255), thickness=1, lineType=cv2.LINE_AA)

    meta = {
        "count1": count1, "results1": results1, "center1": center1,
        "count2": count2, "results2": results2, "center2": center2,
        "c1": c1, "c2": c2, "c3": c3
    }
    return image, meta

# --- usage as before (keeps interactive show) ---
if __name__ == "__main__":
    # โฟลเดอร์ที่มีรูป source ตั้งต้น
    source_dir = os.path.dirname(source)
    valid_ext = {".jpg", ".jpeg", ".png", ".bmp"}
    image_files = [f for f in os.listdir(source_dir)
                   if os.path.splitext(f.lower())[1] in valid_ext]
    image_files.sort()

    if not image_files:
        raise SystemExit(f"No images found in: {source_dir}")

    print(f"Found {len(image_files)} source images in {source_dir}")
    print("Controls: Right / 'd' = next, Left / 'a' = prev, q or Esc = quit")

    idx = 0
    while True:
        current_path = os.path.join(source_dir, image_files[idx])
        source_img = cv2.imread(current_path)
        if source_img is None:
            print(f"Skip unreadable image: {current_path}")
            # ไปภาพถัดไป
            idx = (idx + 1) % len(image_files)
            continue

        out_img, info = match_and_annotate(template1_img, template2_img, source_img, dll_path=dll_path)
        h, w = source_img.shape[:2]
        disp = out_img
        # ย่อถ้าภาพใหญ่มาก (ปรับได้)
        max_w = 1280
        if w > max_w:
            scale = max_w / w
            disp = cv2.resize(out_img, (int(w * scale), int(h * scale)))

        print(f"[{idx+1}/{len(image_files)}] {image_files[idx]}")
        print(f"  Template1: count={info['count1']} center={info['center1']}")
        print(f"  Template2: count={info['count2']} center={info['center2']}")

        win_name = "Matches (Left/Right or a/d to navigate, q/Esc to quit)"
        cv2.imshow(win_name, disp)
        key = cv2.waitKey(0) & 0xFF

        # q หรือ ESC ออก
        if key in (ord('q'), 27):
            break
        # ขวา หรือ d
        elif key in (ord('d'), ord('D'), 83):  # 83 = Right arrow บน Linux
            idx = (idx + 1) % len(image_files)
        # ซ้าย หรือ a
        elif key in (ord('a'), ord('A'), 81):  # 81 = Left arrow
            idx = (idx - 1) % len(image_files)
        else:
            # ปุ่มอื่น = ไปต่อภาพถัดไป (ปรับได้)
            idx = (idx + 1) % len(image_files)

    cv2.destroyAllWindows()
