## 1. 重現與修正

- [x] 1.1 獨立測試角色建立正反案例，修前 50 案得到 28 failed、22 passed。
- [x] 1.2 修正自己新增內容的欄位驗證捷徑，保留既有 schema、編號與完成算法；更新 reason help。
- [x] 1.3 獨立測試角色完成 71 案；Windows／實際 WSL Linux 的五檔回歸各 158 passed。

## 2. 安裝與實測

- [x] 2.1 重建 wheel，以不同隔離 runtime 安裝，不覆寫原安裝；保存 wheel hash 與案例切換紀錄。
- [x] 2.2 完整 Windows／Linux 回歸與 OpenSpec strict validation。
- [x] 2.3 實際新 wheel 指令驗證拒絕非法修改、合法修改可繼續、案例原始測試內容不變。
- [x] 2.4 更新實測報告，區分本工具缺陷、控制器問題與合成軟體問題；保留所有失敗歷史。
