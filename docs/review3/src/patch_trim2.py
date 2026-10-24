from pathlib import Path
H = Path(__file__).resolve().parent

s = (H / "docbuilder.py").read_text(encoding="utf-8")
s = s.replace("            c.paragraphs[0].paragraph_format.space_after = Pt(0)\n            self._runs(c.paragraphs[0], h, size=size, bold=True, color=INK)",
              "            c.paragraphs[0].paragraph_format.space_after = Pt(0)\n            c.paragraphs[0].paragraph_format.keep_with_next = True\n            self._runs(c.paragraphs[0], h, size=size, bold=True, color=INK)")
(H / "docbuilder.py").write_text(s, encoding="utf-8")

r = (H / "rc3b.py").read_text(encoding="utf-8")
r = r.replace('    d.p(F["bench_text"], align="justify")',
              '    for part in F["bench_text"].split("**Guard elision.**"):\n        d.p(part if part is F["bench_text"].split("**Guard elision.**")[0] else "**Guard elision.** " + part.strip(), align="justify")')
r = r.replace('    d.p(F["studio_text"], align="justify")',
              '    d.p(F["studio_intro"], align="justify")\n    d.bullets(F["studio_parts"], size=9.5)')
(H / "rc3b.py").write_text(r, encoding="utf-8")

t = (H / "report_texts.py").read_text(encoding="utf-8")
a = t.index('    F["studio_text"] = (')
b = t.index('    F["stress_results_text"]')
new = '''    F["studio_intro"] = ("Each project ran through the real application path (the HTTP API the UI uses) on a clean server with no LLM key and a cold build cache. "
                         "A function counts as *accelerated* only if every replayed call matched and its measured speedup was at least 1.1x. The row marked \\"before print fix\\" is the "
                         "first TextLab run, whose output hash differed until commit `bd7e8ca`.")
    F["studio_parts"] = parts
    F["studio_text"] = F["studio_intro"]
'''
t = t[:a] + new + t[b:]
(H / "report_texts.py").write_text(t, encoding="utf-8")
print("ok")
