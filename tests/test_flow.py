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
        with self.assertRaisesRegex(DomainError,"审定"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        review_id=self.db.submit_review(variant,self.editor)
        self.db.decide_review(review_id,self.reviewer,"approved","拟句与残片行款相合，可定")
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
    def test_review_return_revise_resubmit_and_approve(self):
        variant=self.db.create_variant(self.passage,self.w2,"春水东流，故人南去。","按语义补足",self.editor,0)
        with self.assertRaisesRegex(DomainError,"无权"):
            self.db.submit_review(variant,self.outsider)
        rid=self.db.submit_review(variant,self.editor)
        with self.assertRaisesRegex(DomainError,"待审"):
            self.db.update_variant(variant,"送审中改动","不应允许",self.editor,1)
        with self.assertRaisesRegex(DomainError,"意见"):
            self.db.decide_review(rid,self.reviewer,"returned","")
        with self.assertRaisesRegex(DomainError,"无权"):
            self.db.decide_review(rid,self.outsider,"approved","外部人员无权审定")
        self.assertEqual("returned",self.db.decide_review(rid,self.reviewer,"退回","拟句缺少版本依据，退回补证"))
        with self.assertRaisesRegex(DomainError,"修订"):
            self.db.submit_review(variant,self.editor)
        self.db.update_variant(variant,"春水东流，故人南逝。","据乙本残片改去为逝",self.editor,1)
        rid2=self.db.submit_review(variant,self.owner,on_behalf_of=self.editor)
        self.assertEqual("approved",self.db.decide_review(rid2,self.reviewer,"通过","补证充分，可定为该版本定本"))
        groups=self.db.list_reviews(self.work,self.owner)
        self.assertEqual(0,len(groups["pending"])); self.assertEqual(1,len(groups["returned"])); self.assertEqual(1,len(groups["approved"]))
        self.assertEqual("编辑",groups["approved"][0]["on_behalf_of_name"])
        exported=self.db.export_collation(self.work,self.reviewer)
        self.assertTrue(exported["passages"][0]["variants"][0]["is_definitive"])
        self.db.lock_passage(self.passage,self.owner,"定稿")
    def test_withdraw_and_lock_gating(self):
        variant=self.db.create_variant(self.passage,self.w2,"拟句一","理由充分",self.editor,0)
        rid=self.db.submit_review(variant,self.editor)
        with self.assertRaisesRegex(DomainError,"项目负责人"):
            self.db.withdraw_review(rid,self.editor)
        with self.assertRaisesRegex(DomainError,"待审"):
            self.db.lock_passage(self.passage,self.owner)
        self.db.withdraw_review(rid,self.owner)
        with self.assertRaisesRegex(DomainError,"撤回"):
            self.db.decide_review(rid,self.reviewer,"approved","已撤回的送审")
        with self.assertRaisesRegex(DomainError,"审定"):
            self.db.lock_passage(self.passage,self.owner)
        rid2=self.db.submit_review(variant,self.editor)
        self.db.decide_review(rid2,self.reviewer,"approved","可以通过")
        self.db.lock_passage(self.passage,self.owner,"定稿")
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.submit_review(variant,self.editor)

if __name__=="__main__": unittest.main()
