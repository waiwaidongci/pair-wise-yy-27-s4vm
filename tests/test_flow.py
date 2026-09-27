import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import CollationDB, DomainError

class CollationFlowTest(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd); self.db=CollationDB(self.path)
        self.owner=self.db.add_user("负责人","owner"); self.editor=self.db.add_user("编辑","editor"); self.reviewer=self.db.add_user("审阅","reviewer"); self.outsider=self.db.add_user("外部","reviewer")
        self.work=self.db.create_work("残卷","异文比较",self.owner)
        self.w1=self.db.add_witness(self.work,"甲本","version"); self.w2=self.db.add_witness(self.work,"乙本","fragment","馆藏残片","中段缺页")
        self.db.grant_witness_editor(self.w2,self.editor,self.owner); self.db.grant_work_access(self.work,self.reviewer,"review",self.owner)
        self.passage=self.db.add_passage(self.work,"第一节","春水东流，故人南去。",self.owner)
        self.db.align_passage(self.passage,self.w1,"春水东流，故人南去。",1,self.owner)
        self.db.align_passage(self.passage,self.w2,"春水东流，[缺页]",2,self.editor)
    def tearDown(self): self.db.close(); os.unlink(self.path)
    def test_multilayer_revision_snapshot_export_and_lock(self):
        variant=self.db.create_variant(self.passage,self.w2,"春水东流，故人南去。","按语义补足",self.editor,0)
        rev=self.db.update_variant(variant,"春水东流，[不可辨]人南去。","墨迹受损，不再直接补写",self.editor,1)
        self.assertEqual(2,rev)
        snap=self.db.get_snapshot(self.passage,2,self.owner)
        self.assertEqual(2,snap["layer"])
        exported=self.db.export_collation(self.work,self.reviewer)
        self.assertEqual(1,exported["gap_count"])
        self.assertTrue(exported["passages"][0]["variants"][0]["notes"] == [])
        review=self.db.submit_for_review(variant,self.editor)
        self.db.decide_review(review,self.reviewer,"approved","异文成立，定为本版本定本")
        self.db.lock_passage(self.passage,self.owner,"定稿")
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.update_variant(variant,"另一文本","无意义修改",self.editor,2)
    def test_optimistic_lock_permission_and_mark_validation(self):
        first=self.db.create_variant(self.passage,self.w2,"补足一","理由一",self.editor,0)
        with self.assertRaisesRegex(DomainError,"版本冲突"):
            self.db.create_variant(self.passage,self.w2,"补足二","理由二",self.editor,0)
        with self.assertRaisesRegex(DomainError,"无权"):
            self.db.create_variant(self.passage,self.w2,"补足三","理由三",self.reviewer,1)
        with self.assertRaisesRegex(DomainError,"无权"):
            self.db.export_collation(self.work,self.outsider)
        with self.assertRaisesRegex(DomainError,"括号"):
            self.db.align_passage(self.passage,self.w1,"文本[未闭合",9,self.owner)

class ReviewFlowTest(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd); self.db=CollationDB(self.path)
        self.owner=self.db.add_user("负责人","owner"); self.editor=self.db.add_user("编辑","editor")
        self.reviewer=self.db.add_user("审阅","reviewer"); self.outsider=self.db.add_user("外部","reviewer")
        self.work=self.db.create_work("残卷","审定流程",self.owner)
        self.w1=self.db.add_witness(self.work,"甲本","version"); self.w2=self.db.add_witness(self.work,"乙本","fragment")
        self.db.grant_witness_editor(self.w2,self.editor,self.owner)
        self.db.grant_work_access(self.work,self.reviewer,"review",self.owner)
        self.passage=self.db.add_passage(self.work,"第一节","原句文本",self.owner)
        self.db.align_passage(self.passage,self.w1,"原句文本",1,self.owner)
        self.db.align_passage(self.passage,self.w2,"[缺页]",2,self.editor)
        self.variant=self.db.create_variant(self.passage,self.w2,"拟句文本","综合文献补足",self.editor,0)
    def tearDown(self): self.db.close(); os.unlink(self.path)

    def _submit_decide(self, action, comment):
        rid=self.db.submit_for_review(self.variant,self.editor)
        self.db.decide_review(rid,self.reviewer,action,comment); return rid

    def test_submit_permissions_and_duplicate(self):
        with self.assertRaisesRegex(DomainError,"送审"):
            self.db.submit_for_review(self.variant,self.outsider)
        rid=self.db.submit_for_review(self.variant,self.editor)
        # 负责人可代送，但已有待审时不能重复
        v2=self.db.create_variant(self.passage,self.w1,"甲本异文","甲本理由充分",self.owner,1)
        rid_owner=self.db.submit_for_review(v2,self.owner)
        self.assertTrue(rid_owner)
        with self.assertRaisesRegex(DomainError,"待审"):
            self.db.submit_for_review(self.variant,self.owner)
        # 审阅人不能自己送审
        with self.assertRaisesRegex(DomainError,"送审"):
            self.db.submit_for_review(self.variant,self.reviewer)
        self.assertTrue(rid)

    def test_reviewer_sees_original_proposal_and_reason(self):
        rid=self.db.submit_for_review(self.variant,self.editor)
        groups=self.db.list_reviews(self.work,self.reviewer)
        pending=groups["pending"][0]
        self.assertEqual(rid,pending["id"])
        self.assertEqual("原句文本",pending["base_text"])
        self.assertEqual("[缺页]",pending["aligned_text"])
        self.assertEqual("拟句文本",pending["proposed_text"])
        self.assertEqual("综合文献补足",pending["reason"])

    def test_decision_requires_review_permission_and_comment(self):
        rid=self.db.submit_for_review(self.variant,self.editor)
        with self.assertRaisesRegex(DomainError,"审阅权限"):
            self.db.decide_review(rid,self.outsider,"approved","可以")
        with self.assertRaisesRegex(DomainError,"审阅权限"):
            self.db.decide_review(rid,self.owner,"approved","负责人也不能自审")
        with self.assertRaisesRegex(DomainError,"意见"):
            self.db.decide_review(rid,self.reviewer,"approved","  ")
        self.db.decide_review(rid,self.reviewer,"approved","文本与证据相合")
        with self.assertRaisesRegex(DomainError,"已经审定"):
            self.db.decide_review(rid,self.reviewer,"returned","不能重复审定")

    def test_returned_variant_must_be_revised_before_resubmit(self):
        rid=self._submit_decide("returned","补字依据不足，请参照纸背")
        groups=self.db.list_reviews(self.work,self.editor)
        self.assertEqual(rid,groups["returned"][0]["id"])
        with self.assertRaisesRegex(DomainError,"先修订"):
            self.db.submit_for_review(self.variant,self.editor)
        self.db.update_variant(self.variant,"修订拟句","纸背墨迹印证补字",self.editor,1)
        rid2=self.db.submit_for_review(self.variant,self.editor)
        self.db.decide_review(rid2,self.reviewer,"approved","修订后可从")
        groups=self.db.list_reviews(self.work,self.owner)
        self.assertEqual(1,len(groups["approved"])); self.assertEqual(1,len(groups["returned"]))
        with self.assertRaisesRegex(DomainError,"定本"):
            self.db.update_variant(self.variant,"再改一版","还想调整",self.editor,2)

    def test_owner_withdraw_pending_only(self):
        rid=self.db.submit_for_review(self.variant,self.editor)
        with self.assertRaisesRegex(DomainError,"负责人"):
            self.db.withdraw_review(rid,self.editor)
        self.db.withdraw_review(rid,self.owner)
        groups=self.db.list_reviews(self.work,self.owner)
        self.assertEqual(rid,groups["withdrawn"][0]["id"])
        with self.assertRaisesRegex(DomainError,"尚未审阅"):
            self.db.withdraw_review(rid,self.owner)
        # 已审定记录不能撤回
        rid2=self.db.submit_for_review(self.variant,self.editor)
        self.db.decide_review(rid2,self.reviewer,"returned","需修改")
        with self.assertRaisesRegex(DomainError,"尚未审阅"):
            self.db.withdraw_review(rid2,self.owner)

    def test_lock_requires_approved_final_with_opinion(self):
        # 没有任何审定记录不能锁
        with self.assertRaisesRegex(DomainError,"尚未送审"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        rid=self.db.submit_for_review(self.variant,self.editor)
        # 待审中不能锁
        with self.assertRaisesRegex(DomainError,"待审"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        self.db.decide_review(rid,self.reviewer,"returned","请再核")
        # 退回未修订不能锁
        with self.assertRaisesRegex(DomainError,"退回"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        self.db.update_variant(self.variant,"修订拟句","已据意见修订",self.editor,1)
        rid2=self.db.submit_for_review(self.variant,self.editor)
        self.db.withdraw_review(rid2,self.owner)
        # 撤回后不能锁
        with self.assertRaisesRegex(DomainError,"撤回"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        rid3=self.db.submit_for_review(self.variant,self.editor)
        self.db.decide_review(rid3,self.reviewer,"approved","依据充分，定为本版本定本")
        self.db.lock_passage(self.passage,self.owner,"版本定稿")
        exported=self.db.export_collation(self.work,self.reviewer)
        p=exported["passages"][0]
        self.assertEqual("locked",p["status"])
        self.assertTrue(p["variants"][0]["is_final"])
        self.assertEqual("修订拟句",p["variants"][0]["final_text"])
        self.assertEqual(self.variant,p["final_readings"][0]["variant_id"])

if __name__=="__main__": unittest.main()
