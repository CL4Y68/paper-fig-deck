
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from kit import _skill_scripts  # noqa: E402
sys.path.insert(0, _skill_scripts())
from svg_to_pptx.drawingml.elements import estimate_single_line_text_frame_width as est
tests = [
    ("纯中文测试一二三四五六", "SimSun", 24),
    ("纯中文测试一二三四五六", "Times New Roman", 24),
    ("Fig. 13 FTIR", "Times New Roman", 24),
    ("Fig. 13 FTIR", "SimSun", 24),
    ("文献精读", "SimSun", 24),
    ("示例题头文本", "Times New Roman", 24),
]
for text, fam, size in tests:
    w = est([{"text": text, "font_size": size, "font_family": fam}], include_headroom=True)
    print(f"{text!r:30} {fam:16} -> {w:.1f}px  ({w/size:.2f}em avg)")
# mixed: how does it treat CJK in a TNR family run?
w = est([{"text": "Fig. 13 碳化后非纤维区已形成", "font_size": 32, "font_family": "Times New Roman, SimSun"}], include_headroom=True)
print("mixed32 ->", round(w,1))
