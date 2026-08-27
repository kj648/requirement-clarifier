import sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq


class TestValidateRefs(unittest.TestCase):
    def _doc(self, rid="R3"):
        return {"questions": [{"no": 1, "evidence": {"rules_ref": [
            {"id": rid, "doc": "rules/x.md", "text": "已还清的判定：余额清零即视为已还清"}]}}]}

    def _root(self, body):
        d = Path(tempfile.mkdtemp())
        (d / "rules").mkdir()
        (d / "rules" / "x.md").write_text(body, encoding="utf-8")
        return d

    def test_matches_h2_halfwidth_period(self):
        root = self._root("## R3. 已还清的判定：余额清零即视为已还清\n正文\n")
        self.assertEqual(bq.validate_refs(self._doc(), root), [])

    def test_matches_h3_and_fullwidth_separators(self):
        for head in ("### R3． 已还清的判定：余额清零即视为已还清",
                     "## R3： 已还清的判定：余额清零即视为已还清"):
            root = self._root(head + "\n正文\n")
            self.assertEqual(bq.validate_refs(self._doc(), root), [],
                             f"标题格式应被接受: {head}")

    def test_missing_doc_reports_error(self):
        errs = bq.validate_refs(self._doc(), Path(tempfile.mkdtemp()))
        self.assertTrue(any("不存在" in e for e in errs), errs)

    def test_missing_entry_reports_error(self):
        root = self._root("## R1. 别的规则\n")
        errs = bq.validate_refs(self._doc(), root)
        self.assertTrue(any("R3" in e for e in errs), errs)

    def test_drifted_text_reports_error(self):
        """规则文档改过了而题目里的 text 副本没跟上 —— 必须报出来。"""
        root = self._root("## R3. 已还清的判定：改成按状态字段判\n")
        errs = bq.validate_refs(self._doc(), root)
        self.assertTrue(any("不一致" in e for e in errs), errs)


class TestInferRoot(unittest.TestCase):
    def test_infers_project_root_from_json_location(self):
        """rules_ref.doc 相对项目根写,而 json 就在 docs/requirements/ 下面 ——
        项目根一定在它的祖先里,不该逼每个调用点手动传 --root。"""
        j = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                    "/2026-07-11-逾期提醒-r1.json")
        self.assertEqual(bq.infer_root(j).resolve(),
                         (ROOT / "examples/demo-project").resolve())

    def test_falls_back_when_no_docs_requirements_above(self):
        import tempfile
        d = Path(tempfile.mkdtemp())
        (d / "x.json").write_text("{}", encoding="utf-8")
        self.assertEqual(bq.infer_root(d / "x.json"), Path("."))

    def test_example_validates_with_inferred_root(self):
        """端到端:不传 --root,校验也该过。"""
        import json as _json, subprocess, sys as _sys
        j = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                    "/2026-07-11-逾期提醒-r1.json")
        p = subprocess.run([_sys.executable, str(ROOT / "scripts" / "build_questionnaire.py"),
                            str(j), "--check"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class TestExtractFn(unittest.TestCase):
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ctjs", ROOT / "scripts" / "check_template_js.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_single_line_function_is_not_over_captured(self):
        """单行实现的函数,闭合括号不在独立行上 —— 不该把下一个函数一起拖进来。"""
        js = ("function a(x){ return x + 1; }\n"
              "function b(y){\n  return y * 2;\n}\n")
        got = self._mod().extract_fn(js, "a")
        self.assertEqual(got, "function a(x){ return x + 1; }")
        self.assertEqual(got.count("function "), 1)

    def test_multi_line_function_is_captured_whole(self):
        js = "function b(y){\n  if (y) {\n    return 1;\n  }\n  return 2;\n}\nfunction c(){}\n"
        got = self._mod().extract_fn(js, "b")
        self.assertTrue(got.endswith("}"), got)
        self.assertEqual(got.count("function "), 1)
        self.assertIn("return 2;", got)

    def test_missing_function_returns_none(self):
        self.assertIsNone(self._mod().extract_fn("function a(){}", "nope"))

    def test_real_template_whenToDom_is_exactly_one_function(self):
        """对真实模板跑一遍 —— 这条正好能抓住『抠多了』那个 bug。"""
        html = (ROOT / "templates" / "questionnaire.html").read_text(encoding="utf-8")
        m = self._mod()
        fn = m.extract_fn(m.extract_script(html), "whenToDom")
        self.assertIsNotNone(fn)
        self.assertEqual(fn.count("function "), 1, fn[:200])
        self.assertTrue(fn.endswith("}"), fn[-80:])


if __name__ == "__main__":
    unittest.main()
