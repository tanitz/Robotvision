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
source_img = cv2.imread(source)
if template1_img is None:
	raise SystemExit(f"Failed to read template1 image. Please verify the path: {template1}")
if template2_img is None:
	raise SystemExit(f"Failed to read template2 image. Please verify the path: {template2}")
if source_img is None:
	raise SystemExit(f"Failed to read source image. Please verify the path: {source}")


dll_path = mt.find_library_path()
params1 = mt.MatchingParams(maxCount=1, scoreThreshold=0.6, iouThreshold=0.8, angle=5.0)
params2 = mt.MatchingParams(maxCount=1, scoreThreshold=0.4, iouThreshold=0.6, angle=1.0)
matcher1 = mt.create_matcher_for_template(template1_img, dll_path, params1)
matcher2 = mt.create_matcher_for_template(template2_img, dll_path, params2)
count1, results1 , center1= mt.run_match(matcher1, source_img)
count2, results2 , center2 = mt.run_match(matcher2, source_img)
print(f"Template 1 Matches: {count1}, Results: {results1}, Center: {center1}")
print(f"Template 2 Matches: {count2}, Results: {results2}, Center: {center2}")
h, w = source_img.shape[:2]
vis1 = mt.draw_results(source_img, results1)
vis2 = mt.draw_results(source_img, results2)

# --- NEW: draw line between first center of center1 and center2 ---
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

c1 = _first_center(center1)
c2 = _first_center(center2)
c3 = None
if c1 and c2:
    c3 = (int(c1[0]), int(c2[1]))
# create a copy of the source with both match drawings and the connecting line
vis_all = mt.draw_results(source_img.copy(), list(results1) + list(results2))
image = source_img.copy()

if c1 and c2:
    cv2.line(image, c1, c2, (0, 0, 255), thickness=1, lineType=cv2.LINE_AA)
    cv2.circle(image, c1, 3, (0, 255, 0), -1, lineType=cv2.LINE_AA)
    cv2.circle(image, c2, 3, (255, 0, 0), -1, lineType=cv2.LINE_AA)

    # --- compute angle between line C1-C2 and C1-C3 (at point C1) ---
    def angle_between(p1, p2, p3):
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

    if c3:
        ang_signed = angle_between(c1, c2, c3)
        if ang_signed is None:
            ang_text = "angle: n/a"
        else:
            ang_abs = abs(ang_signed)
            ang_text = f"angle: {ang_abs:.1f} deg (signed {ang_signed:.1f})"
        # draw angle text near C1
        txt_pos = (int(c1[0] + 8), int(c1[1] - 10))
        cv2.putText(image, ang_text, txt_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        # optionally draw c3 and connector lines
        cv2.circle(image, c3, 3, (0, 255, 255), -1, lineType=cv2.LINE_AA)
        cv2.line(image, c3, c1, (0, 0, 255), thickness=1, lineType=cv2.LINE_AA)
        cv2.line(image, c3, c2, (0, 0, 255), thickness=1, lineType=cv2.LINE_AA)

# --- END NEW ---

# cv2.imshow('Matches Template 1', cv2.resize(vis1, (w//2, h//2)))
# cv2.imshow('Matches Template 2', cv2.resize(vis2, (w//2, h//2)))
cv2.imshow('Matches - line between centers', cv2.resize(image, (w//2, h//2)))
cv2.waitKey(0)
cv2.destroyAllWindows()
