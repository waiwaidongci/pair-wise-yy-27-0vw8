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
        # 修订后尚未审阅：未决，锁稿应被拒绝并给出数量
        with self.assertRaisesRegex(DomainError,"还有 1 条"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        self.db.review_variant(variant,"adopted","改后稳妥，采用",self.reviewer)
        exported=self.db.export_collation(self.work,self.reviewer)
        v=exported["passages"][0]["variants"][0]
        self.assertEqual("adopted",v["decision"]); self.assertEqual("采用",v["decision_label"])
        self.assertEqual(1,exported["adopted_count"]); self.assertEqual(0,exported["pending_count"])
        self.db.lock_passage(self.passage,self.owner,"定稿")
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.update_variant(variant,"另一文本","无意义修改",self.editor,2)
    def test_review_permission_supersede_and_lock_guard(self):
        viewer=self.db.add_user("仅查看","reviewer")
        self.db.grant_work_access(self.work,viewer,"view",self.owner)
        variant=self.db.create_variant(self.passage,self.w2,"补足一","理由一",self.editor,0)
        # 编辑与仅有 view 权限者不能审阅
        with self.assertRaisesRegex(DomainError,"无权审阅"):
            self.db.review_variant(variant,"adopted","编辑自审",self.editor)
        with self.assertRaisesRegex(DomainError,"无权审阅"):
            self.db.review_variant(variant,"adopted","只能看",viewer)
        # 结论与意见非法
        with self.assertRaisesRegex(DomainError,"结论必须"):
            self.db.review_variant(variant,"待定","再看看",self.reviewer)
        with self.assertRaisesRegex(DomainError,"意见不能为空"):
            self.db.review_variant(variant,"adopted","  ",self.reviewer)
        # 中文结论可用；驳回后导出应标注驳回
        self.db.review_variant(variant,"驳回","依据不足",self.reviewer)
        exported=self.db.export_collation(self.work,self.owner)
        v=exported["passages"][0]["variants"][0]
        self.assertEqual("rejected",v["decision"]); self.assertEqual("驳回",v["decision_label"])
        # 同一审阅人可改写结论，旧记录被自身覆盖
        self.db.review_variant(variant,"adopted","复核后可采用",self.reviewer)
        exported=self.db.export_collation(self.work,self.owner)
        v=exported["passages"][0]["variants"][0]
        self.assertEqual("adopted",v["decision"]); self.assertEqual(1,len(v["reviews"]))
        # 提交新修订层后，旧结论自动失效，异文回到未决
        self.db.update_variant(variant,"补足一新层","理由更新版",self.editor,1)
        exported=self.db.export_collation(self.work,self.reviewer)
        v=exported["passages"][0]["variants"][0]
        self.assertEqual("pending",v["decision"]); self.assertEqual("未决",v["decision_label"])
        self.assertEqual([],v["reviews"]); self.assertEqual(2,len(v["superseded_reviews"]))
        self.assertEqual(1,exported["pending_count"])
        with self.assertRaisesRegex(DomainError,"还有 1 条"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        # 新层重新审阅后方可锁稿；锁定后不能再审阅
        self.db.review_variant(variant,"rejected","新层仍不妥",self.reviewer)
        self.db.lock_passage(self.passage,self.owner,"定稿")
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.review_variant(variant,"adopted","锁定后改判",self.reviewer)
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

if __name__=="__main__": unittest.main()
