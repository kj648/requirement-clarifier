import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
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


if __name__ == "__main__":
    unittest.main()
