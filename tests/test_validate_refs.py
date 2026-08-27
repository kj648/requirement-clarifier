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


if __name__ == "__main__":
    unittest.main()
