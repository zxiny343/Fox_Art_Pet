import io, re, os

src = r"C:\Users\zxiny\.workbuddy\projects\c-Users-zxiny-WorkBuddy-2026-11-01-00-53-44\b01d0f3d-c7f1-49e0-805e-deee073f3662\tool-results\chatcmpl-tool-8b3843b0821099ad.txt"
out = r"C:\Users\zxiny\WorkBuddy\2026-11-01-00-53-44\v14_order.txt"

s = io.open(src, encoding="utf-8").read()
# strip XML-ish tags but keep line structure
s = re.sub(r"<Heading[^>]*level=\"(\d)\"[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", s)
s = re.sub(r"</?Heading[^>]*>", "", s)
s = re.sub(r"<TableRow[^>]*>", "\n| ", s)
s = re.sub(r"<TableCell[^>]*>", " ", s)
s = re.sub(r"</TableCell>", " | ", s)
s = re.sub(r"<[^>]+>", "", s)
s = s.replace("\\", "")
lines = [ln.strip() for ln in s.split("\n")]
lines = [ln for ln in lines if ln]
txt = "\n".join(lines)
io.open(out, "w", encoding="utf-8").write(txt)
print("chars", len(txt), "lines", len(lines))
print("OUT", out)
