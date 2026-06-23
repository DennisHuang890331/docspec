# 字型授權與來源（docspec export 字型）

`docspec setup` 從以下 OFL/開放來源下載字型到 `data_dir/fonts/`（每來源的 zip
sha256 釘在 `src/dspx/commands/setup.py` 的 `_FONT_MANIFEST`，下載後 byte 級驗證）。
本檔記錄來源與授權；實際 OFL 全文隨各上游 zip 內 LICENSE 一併取得。

| 字型 | 版本 | 授權 | 來源 |
|---|---|---|---|
| Source Serif 4 (Regular/Bold/It/BoldIt) | 4.005R | SIL OFL 1.1 | https://github.com/adobe-fonts/source-serif/releases/download/4.005R/source-serif-4.005_Desktop.zip |
| Source Sans 3 (Regular/Bold/It/BoldIt) | 3.052R | SIL OFL 1.1 | https://github.com/adobe-fonts/source-sans/releases/download/3.052R/OTF-source-sans-3.052R.zip |
| Source Code Pro (Regular/Bold/It/BoldIt) | 2.042R-u | SIL OFL 1.1 | https://github.com/adobe-fonts/source-code-pro/releases/download/2.042R-u/1.062R-i/1.026R-vf/OTF-source-code-pro-2.042R-u_1.062R-i.zip |
| Source Han Sans TC (思源黑, Regular/Bold) | 2.005R | SIL OFL 1.1 | https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/10_SourceHanSansTC.zip |
| Source Han Serif TC (思源宋, Regular + SemiBold; 內文＋emphasis 粗體 fallback) | 2.003R | SIL OFL 1.1 | https://github.com/adobe-fonts/source-han-serif/releases/download/2.003R/10_SourceHanSerifTC.zip |
| TW-Kai 全字庫正楷體 (TW-Kai-98_1.ttf；標題預設) | 98.1 | 政府資料開放授權 1.0 或 SIL OFL 1.1（任選） | https://www.cns11643.gov.tw/opendata/Fonts_Kai.zip |
| TW-Sung 全字庫正宋體 (TW-Sung-98_1.ttf；內文預設) | 98.1 | 政府資料開放授權 1.0 或 SIL OFL 1.1（任選） | https://www.cns11643.gov.tw/opendata/Fonts_Sung.zip |
| LXGW WenKai TC 霞鶩文楷 (LXGWWenKaiTC-Regular.ttf；內文候選) | 1.522 | SIL OFL 1.1 | https://github.com/lxgw/LxgwWenkaiTC/releases/download/v1.522/lxgw-wenkai-tc-v1.522.zip |

升級＝改 `_FONT_MANIFEST` 的 version＋url，重新抓 zip 的 sha256（仿 TinyTeX 釘法）。
※全字庫 gov 來源為「不帶版本的 latest」URL，政府改檔時 sha256 會漂；不符時重抓並更新 hash。

SIL OFL 1.1 全文：https://openfontlicense.org/
政府資料開放授權條款 1.0：https://data.gov.tw/license
