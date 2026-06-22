-- docspec-tables.lua
-- 表格 → GitHub 渲染 markdown 風（淺灰細線「全格」＝每格四周細邊框、表頭淺灰底、隔列淡底）。
-- 線很細很淡（docspecRule≈#D0D7DE、\arrayrulewidth≈0.4pt），不是 Excel 粗黑格、也不是純三線。
-- 表頭與偶數列同一淡灰底（docspecZebra≈#F6F8FA、GitHub 就這樣），cell padding 舒服。
-- 保留：xltabular 可跨頁（\endhead 跨頁表頭重複）、整表夾在 \linewidth 內、無欄被裁。
-- ★欄寬＝照抄瀏覽器/GitHub「CSS automatic table layout」（min-content / max-content），
--   讓檔名/code 等「原子欄」拿自然寬、整個 token 一行顯示完整，散文/CJK 欄才換行——
--   詳細演算法見下方 colspec 前的大段註解。長 token 的 / _ 斷點仍在 cell 內注入，但只在
--   極端寬表（原子欄加總就超頁寬）才真的派上用場；一般表檔名一定完整。

-- 表格旋鈕（docspec format-config 經 pandoc -M 傳入；缺＝現狀預設＝byte-identical）：
--   docspec-table-size    窄表內文字級 pt（預設 12；寬表＝此值-1）
--   docspec-table-colrules on|off（直欄線開關；預設 on）
-- ★table.size 變動時，下方 fontsize 與 colspec 的 EM 欄寬常數**一起**以 12pt 為錨等比例縮放，
--   否則欄寬以錯字級估算而爆版（design 點名的真耦合）。
-- 表格旋鈕（OPTS）由 Meta 過濾器先填（兩段式 filter：見檔尾 return）。預設＝現狀＝byte-identical。
-- ★不可走 PANDOC_DOCUMENT（此 pandoc 版該全域為 nil）；Meta() 一定在 Table() 之前跑（檔尾兩段
--   filter 保證 Meta 段整段先於 Table 段），故 OPTS 在 Table() 時已填妥。
local OPTS = { narrow = 12, wide = 11, colrules = true }
local function capture_meta(m)
  local function s(key, default)
    if m[key] ~= nil then return pandoc.utils.stringify(m[key]) end
    return default
  end
  local narrow = tonumber(s('docspec-table-size', '12')) or 12
  OPTS.narrow = narrow
  OPTS.wide = narrow - 1
  OPTS.colrules = s('docspec-table-colrules', 'on') ~= 'off'
  return m
end

local function disp_width(s)
  local w = 0
  for _, c in utf8.codes(s) do
    if c >= 0x1100 and (c <= 0x115F
        or (c >= 0x2E80 and c <= 0xA4CF) or (c >= 0xAC00 and c <= 0xD7A3)
        or (c >= 0xF900 and c <= 0xFAFF) or (c >= 0xFF00 and c <= 0xFF60)
        or (c >= 0x20000 and c <= 0x3FFFD)) then
      w = w + 2
    else
      w = w + 1
    end
  end
  return w
end

-- escape LaTeX 特殊字（單一 token）
local function esc(t)
  return (t:gsub('([\\{}%$&#%^_~%%])', function(c)
    local m = {
      ['\\'] = '\\textbackslash{}', ['{'] = '\\{', ['}'] = '\\}', ['$'] = '\\$',
      ['&'] = '\\&', ['#'] = '\\#', ['^'] = '\\textasciicircum{}',
      ['_'] = '\\_', ['~'] = '\\textasciitilde{}', ['%'] = '\\%',
    }
    return m[c]
  end))
end

-- 切「分隔段」：以 / 和 _ 為界，把字串切成段；分隔符黏在『前段尾』。
-- 回傳 { 段字串, ... }（已是 escape 前的原始片段）。
local function split_on_seps(t)
  local segs, buf = {}, {}
  for i = 1, #t do
    local ch = t:sub(i, i)
    buf[#buf + 1] = ch
    if ch == '/' or ch == '_' then
      segs[#segs + 1] = table.concat(buf); buf = {}
    end
  end
  if #buf > 0 then segs[#segs + 1] = table.concat(buf) end
  if #segs == 0 then segs = { t } end
  return segs
end

-- 表格 cell：可斷的等寬（無底）。escape + 在 / 與 _ 後插 \allowbreak；長純英數段包 \seqsplit
-- 逐字可斷（cell 用 \dspxcellcode 非盒，\seqsplit 能在窄欄真的斷字，防溢出）。
local function code_breakable_inner(t)
  local out = {}
  for _, seg in ipairs(split_on_seps(t)) do
    local core, sep = seg, ''
    local last = seg:sub(-1)
    if last == '/' or last == '_' then core, sep = seg:sub(1, -2), last end
    if #core >= 12 and core:match('^[%w]+$') then
      out[#out + 1] = '\\seqsplit{' .. core .. '}'
    else
      out[#out + 1] = esc(core)
    end
    if sep ~= '' then out[#out + 1] = esc(sep) .. '\\allowbreak{}' end
  end
  return table.concat(out)
end
local function breakable_code(t)
  return '\\dspxcellcode{' .. code_breakable_inner(t) .. '}'
end

-- prose 行內 code：每『小塊』各自一個淺灰底 \colorbox（\dspxcodeseg），塊間 \allowbreak。
-- \colorbox 本身不可斷 → 必須讓每塊夠窄：(a) 在大量自然邊界後切塊（分隔符黏前塊尾，故
-- 灰底連續成一條帶）；(b) 任何連續無邊界的長字串硬性每 maxrun 個 byte 再切一次。
-- 於是長 code（pip install "eclipse-zenoh>=1.0"、sample.payload.to_string() 等）能斷在
-- 任一塊邊界、絕不凸出右界；短 code 仍是一塊連續灰底。
local PROSE_BREAK_AFTER = {}
for ch in ('/_.,:;=()[]{}|<>*&!?@ "\''):gmatch('.') do PROSE_BREAK_AFTER[ch] = true end
local PROSE_MAXRUN = 6  -- 無邊界長字串每 6 顯示寬度強制切，確保單塊不寬到溢出

-- 切塊必須走「完整 UTF-8 字元」為單位：以前用逐 byte + runlen>=N 在 lead byte 處 flush，
-- 會把 CJK（3 byte）攔腰切斷 → 半個字進前塊、半個進後塊 → 渲染成 U+FFFD 豆腐。
-- 改成 utf8.codes 逐「碼點」累積：邊界字（PROSE_BREAK_AFTER）後可斷；連續無邊界字串
-- 依「顯示寬度」（CJK=2、拉丁=1）累到 maxrun 才硬切，且永遠在字元邊界 flush，絕不切到字中。
local function prose_code_segments(t)
  local out, buf, runw = {}, {}, 0
  local function flush()
    if #buf > 0 then
      out[#out + 1] = '\\dspxcodeseg{' .. esc(table.concat(buf)) .. '}'
      buf, runw = {}, 0
    end
  end
  -- t 可能含無效 byte 序列（極少數）；utf8.codes 會丟錯，故 pcall 包覆、失敗退回整塊不切。
  local ok = pcall(function()
    for _, cp in utf8.codes(t) do
      local ch = utf8.char(cp)
      buf[#buf + 1] = ch
      if #ch == 1 and PROSE_BREAK_AFTER[ch] then
        flush(); out[#out + 1] = '\\allowbreak{}'        -- 邊界後可斷
      else
        -- 寬字（CJK）權重 2、其餘 1；累到 maxrun 在「此完整字元之後」硬切
        runw = runw + ((cp >= 0x1100 and (cp <= 0x115F
          or (cp >= 0x2E80 and cp <= 0xA4CF) or (cp >= 0xAC00 and cp <= 0xD7A3)
          or (cp >= 0xF900 and cp <= 0xFAFF) or (cp >= 0xFF00 and cp <= 0xFF60)
          or (cp >= 0x20000 and cp <= 0x3FFFD))) and 2 or 1)
        if runw >= PROSE_MAXRUN then
          flush(); out[#out + 1] = '\\allowbreak{}'      -- 長無邊界字串硬切（字元邊界）
        end
      end
    end
  end)
  if not ok then
    -- 退路：無法解碼則整塊一個 colorbox（不硬切，至少不產生半字豆腐）
    out = { '\\dspxcodeseg{' .. esc(t) .. '}' }
    return table.concat(out)
  end
  flush()
  return table.concat(out)
end

-- 純文字：在每個 _ 之後插入可斷行點（讓 ENUM 如 INTERACTIVE_HIGH 能換行）
local function break_underscores(s)
  local out, pos = {}, 1
  while true do
    local i = s:find('_', pos, true)
    if not i then
      out[#out + 1] = pandoc.Str(s:sub(pos)); break
    end
    out[#out + 1] = pandoc.Str(s:sub(pos, i))
    out[#out + 1] = pandoc.RawInline('latex', '\\allowbreak{}')
    pos = i + 1
  end
  return out
end

local function cell_to_latex(cell)
  local doc = pandoc.Pandoc(cell.contents):walk{
    Code = function(c) return pandoc.RawInline('latex', breakable_code(c.text)) end,
    Str = function(s)
      if s.text:find('_', 1, true) then return break_underscores(s.text) end
    end,
  }
  return (pandoc.write(doc, 'latex'):gsub('%s+$', ''))
end

-- 從一段「已注入的 LaTeX」還原可見文字（去命令、去括號、還原 escape），用來估顯示寬。
-- ★關鍵：pandoc 套用 inline 過濾器（本檔的 Code()）早於 block 過濾器（Table()），
-- 所以 Table() 掃描 cell 時，原本的 `code`/檔名 已被換成 RawInline('latex', '\dspxcodeseg{…}')。
-- stringify/walk-Code 都讀不到它 → 長檔名欄被量成寬度 0、塌成窄欄、檔名被硬斷（本次 bug 根因）。
-- 故這裡把 RawInline 的 LaTeX 反推回可見字元（\dspxcodeseg{Vehicl}\allowbreak{}… → VehicleFleet…）。
local function latex_visible(s)
  s = s:gsub('\\allowbreak%s*{}', '')          -- 斷點命令：無寬
  s = s:gsub('\\seqsplit', '')                 -- \seqsplit{...} → 留內容
  s = s:gsub('\\dspx%a*', '')                  -- \dspxcodeseg / \dspxcellcode → 留內容
  s = s:gsub('\\textbf', ''):gsub('\\textit', ''):gsub('\\texttt', '')
  s = s:gsub('\\colorbox%s*{[^}]*}', '')       -- \colorbox{color} 的色名參數丟掉
  s = s:gsub('\\strut', '')
  -- 還原常見 escape（順序：先還原 \textbackslash 再處理單字元 escape）
  s = s:gsub('\\textbackslash{}', '\\')
  s = s:gsub('\\textasciitilde{}', '~'):gsub('\\textasciicircum{}', '^')
  s = s:gsub('\\([%$&#_~%%{}])', '%1')         -- \_ \& \# \$ \% \{ \} \~ → 字元
  s = s:gsub('[{}]', '')                        -- 剩餘括號（群組/命令參數邊界）：無寬
  s = s:gsub('\\%a+%s*', '')                    -- 任何殘留 \command：丟
  return s
end

-- cell 純文字（量寬用）：用 :walk 收 Str/Code/Math/RawInline/空白。
-- 不單用 pandoc.utils.stringify——它對 RawInline（見上）與「**`code`**」都回空字串。
local function cell_text(cell)
  local buf = {}
  pandoc.Pandoc(cell.contents):walk{
    Str = function(s) buf[#buf + 1] = s.text return s end,
    Code = function(c) buf[#buf + 1] = c.text return c end,
    Math = function(m) buf[#buf + 1] = m.text return m end,
    RawInline = function(r) buf[#buf + 1] = latex_visible(r.text) return r end,
    Space = function(x) buf[#buf + 1] = ' ' return x end,
    SoftBreak = function(x) buf[#buf + 1] = ' ' return x end,
    LineBreak = function(x) buf[#buf + 1] = ' ' return x end,
  }
  return table.concat(buf)
end

-- escape LaTeX 特殊字（給表頭純文字用，避免碰到已注入的 \allowbreak 等命令）
local function escape_plain(t)
  return (t:gsub('([\\{}%$&#%^_~%%])', function(c)
    local m = {
      ['\\'] = '\\textbackslash{}', ['{'] = '\\{', ['}'] = '\\}', ['$'] = '\\$',
      ['&'] = '\\&', ['#'] = '\\#', ['^'] = '\\textasciicircum{}',
      ['_'] = '\\_', ['~'] = '\\textasciitilde{}', ['%'] = '\\%',
    }
    return m[c]
  end))
end

-- 表頭：純文字逐 token escape，長英文字母串（>=9）外包 \seqsplit 讓窄欄逐字換行；
-- 非字母分隔（_、/、空白）原樣保留並提供斷點。必須在純文字上做，避免誤切已注入命令。
local function header_latex(cell)
  local txt = cell_text(cell)
  local out, pos = {}, 1
  while pos <= #txt do
    local s, e = txt:find('%a+', pos)
    if not s then
      out[#out + 1] = escape_plain(txt:sub(pos)); break
    end
    if s > pos then out[#out + 1] = escape_plain(txt:sub(pos, s - 1)) end
    local run = txt:sub(s, e)
    if #run >= 9 then
      out[#out + 1] = '\\seqsplit{' .. run .. '}'
    else
      out[#out + 1] = run
    end
    pos = e + 1
  end
  return '\\textbf{' .. table.concat(out) .. '}'
end

local function row_latex(row, header)
  local parts = {}
  for _, cell in ipairs(row.cells) do
    if header then
      parts[#parts + 1] = header_latex(cell)
    else
      parts[#parts + 1] = cell_to_latex(cell)
    end
  end
  return table.concat(parts, ' & ') .. ' \\\\'
end

-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║ 欄寬演算法：照抄瀏覽器/GitHub「CSS automatic table layout」              ║
-- ╠══════════════════════════════════════════════════════════════════════╣
-- 舊法（已棄）：所有欄一律 `>{\hsize=…}X` 等比攤整頁寬 → 長檔名/code 被硬塞進窄欄、
-- 在 / _ 處被切成兩三段、超醜。GitHub 不這樣：它給每欄算 min-content / max-content，
-- 表寬不足時「優先壓可 wrap 的散文/CJK 欄」，讓「原子欄」（檔名/code/短標籤）維持自然
-- 寬度、整個 token 一行顯示完整。本演算法重現該行為：
--
-- 每欄量兩個寬度（顯示寬度單位：CJK=2、拉丁=1）：
--   • max-content（maxc[i]）＝整格不換行的寬度（取該欄各格最大）。
--   • 最長「原子 token」（atom[i]）＝該欄各格中、最長一段「不該斷」的連續串：
--       拉丁字母/數字/`_`/`/`/`.`/`-`/`:`（檔名、key 路徑、ENUM、版號）算同一 token；
--       CJK 字與空白「重置」該段（CJK 可任意斷行、空白可換行）。
--       → 檔名 `Vehicle_Fleet_Interface_ICD_v1.0.md` 整串算一個 atom（≈35）；
--         散文「監督營運邊界…」CJK 不斷地累積 → atom 很小（只剩夾在中間的英文字 ODD≈3）。
--
-- 分類：atom[i] 佔 maxc[i] 比重高（≥0.6）＝「原子欄」＝壓不得（壓了就斷 token）；
--       否則＝「散文/CJK 欄」＝可 wrap、吸收剩餘寬。
--
-- 配寬（單位→pt；經實測 \linewidth=468pt、docspec-cas 單欄）：
--   1. 原子欄拿固定自然寬 p{atom 寬 + 一點 slack}（＝整 token 不斷）。
--   2. 散文欄用 tabularx 的 X，依 maxc 權重瓜分「剩餘寬」並換行。
--   3. 若所有原子欄自然寬加總就 > \linewidth（極端寬表，如 ICD 6 欄 QoS）：退而求其次，
--      把原子欄也降級成可 wrap 的 X（其 cell 的 \allowbreak/\seqsplit 才會真的斷），
--      確保不溢出；一般窄表這條不會觸發、檔名一定完整。
--   4. 表寬：自然總寬若 ≤ \linewidth，就用自然總寬（窄表靠左、像 GitHub 不硬撐滿）；
--      超過才鎖 \linewidth + 讓散文欄 wrap。

-- 量一格最長「原子 token」：拉丁/數字/常見 code 標點連成一段，CJK 與空白重置。
-- 回傳 (最長 token 寬, 該最長 token 是否含 code 標點)。含 `_ / { } : ( )` 等＝像
-- 檔名/key 路徑/ENUM（多為等寬 code、常粗體、字較寬）；純字母數字＝像短標籤（Normative，較窄）。
local function atom_width(s)
  local best, cur, best_code, cur_code = 0, 0, false, false
  for _, cp in utf8.codes(s) do
    local is_cjk = cp >= 0x1100 and (cp <= 0x115F
      or (cp >= 0x2E80 and cp <= 0xA4CF) or (cp >= 0xAC00 and cp <= 0xD7A3)
      or (cp >= 0xF900 and cp <= 0xFAFF) or (cp >= 0xFF00 and cp <= 0xFF60)
      or (cp >= 0x20000 and cp <= 0x3FFFD))
    -- 不重置的「同一 token」字元：拉丁字母、數字、_ / . - : { } ( ) +
    local alnum = (cp >= 0x30 and cp <= 0x39) or (cp >= 0x41 and cp <= 0x5A)
      or (cp >= 0x61 and cp <= 0x7A) or cp == 0x2E or cp == 0x2D
    local codep = cp == 0x5F or cp == 0x2F or cp == 0x3A
      or cp == 0x7B or cp == 0x7D or cp == 0x28 or cp == 0x29 or cp == 0x2B
    if is_cjk or cp == 0x20 or cp == 0x09 then
      cur, cur_code = 0, false                   -- CJK / 空白：重置（可斷點）
    elseif alnum or codep then
      cur = cur + 1                              -- 同一原子 token 延續
      if codep then cur_code = true end
    else
      cur, cur_code = 0, false                   -- 其他標點：斷點、重置
    end
    if cur > best then best, best_code = cur, cur_code end
  end
  return best, best_code
end

-- 物理估算（實測 \linewidth=468.33pt、docspec-cas 單欄）：
--   1 顯示單位 ≈ EM pt（CJK=2 單位≈2·EM≈一個漢字寬；拉丁=1 單位≈半個漢字≈一個 code 字）。
--   \small（10.95pt）量到 code 字 ≈5.3pt、\footnotesize（10pt）≈4.8pt；取略寬保險值。
local LINEWIDTH_PT = 468.0
-- 欄分隔＝彩色 \vrule（非裸 `|`）：colortbl 的 \rowcolor 儲存格底色會「蓋過」裸 `|` 直線
-- （橫線 \hline 畫在底色之上故留、直線畫在底色之下故消失——經典坑）。改用 !{...\vrule...}
-- 把直線畫在底色之上，全格網才會真的顯示。\arrayrulewidth/docspecRule 與橫線同寬同色。
-- 直欄線：on＝彩色 \vrule（畫在 \rowcolor 底色之上才可見）；off＝空字串（無直線、橫線仍在）。
local VRULE_ON = '!{\\color{docspecRule}\\vrule width \\arrayrulewidth}'
local function colspec(tbl, ncol, wide, o)
  local VRULE = o.colrules and VRULE_ON or ''
  local maxc, atom, codeish = {}, {}, {}
  for i = 1, ncol do maxc[i], atom[i], codeish[i] = 1, 0, false end
  local function scan(row)
    for i, cell in ipairs(row.cells) do
      if i <= ncol then
        local t = cell_text(cell)
        maxc[i] = math.max(maxc[i], disp_width(t))
        local aw, ac = atom_width(t)
        if aw > atom[i] then atom[i] = aw end
        if ac and aw >= 6 then codeish[i] = true end   -- 該欄出現「含 code 標點的長 token」
      end
    end
  end
  for _, r in ipairs(tbl.head.rows) do scan(r) end
  for _, b in ipairs(tbl.bodies) do for _, r in ipairs(b.body) do scan(r) end end

  -- pt / 顯示單位。原子欄多為等寬 code，常還是粗體（**`code`**）→ 比散文 CJK 略寬，
  -- 故 EM_RIGID > EM_FLEX，確保整個 token（含粗體版）一行塞得下、不擦邊斷。
  -- EM 隨表格字級同步：以「窄表 12pt / 寬表 11pt」為錨等比例縮放（TBL_NARROW/TBL_WIDE 旋鈕）。
  -- 否則欄寬會以錯誤字級估算而爆版/留白。預設 size=12 → 與舊硬寫值相同＝byte-identical。
  local EM_FLEX  = wide and (5.5 * o.wide / 11) or (5.9 * o.narrow / 12)
  local EM_RIGID = wide and (6.25 * o.wide / 11) or (6.65 * o.narrow / 12)
  local PAD = wide and 10.0 or 16.0       -- 每欄 2·\tabcolsep（寬表5pt、窄表8pt；與字級無關）

  -- 分類 + 各欄「想要的自然寬」（pt，含 padding）。
  local rigid, want = {}, {}
  for i = 1, ncol do
    rigid[i] = atom[i] >= 6 and atom[i] >= maxc[i] * 0.6   -- 原子 token 主導該欄
    if rigid[i] then
      -- code-ish 原子欄（檔名/key/ENUM、等寬常粗體）用較寬 EM；純字母短標籤（Normative）用 EM_FLEX。
      -- +2 單位 slack：粗體 token（**IDLE_NOT_READY**、粗體大寫比例字較寬）常擦邊、差幾 pt 就斷，多給保險。
      local em = codeish[i] and EM_RIGID or EM_FLEX
      want[i] = (atom[i] + 2) * em + PAD                    -- 整 token 一行（+slack）
    else
      want[i] = maxc[i] * EM_FLEX + PAD                     -- 散文：理想是整段不換行
    end
  end

  -- 原子欄固定寬加總；散文欄為彈性。
  local rigid_pt, flex_max_pt, nflex = 0, 0, 0
  for i = 1, ncol do
    if rigid[i] then rigid_pt = rigid_pt + want[i]
    else flex_max_pt = flex_max_pt + want[i]; nflex = nflex + 1 end
  end

  -- 退場：原子欄自然寬就吃光 \linewidth（極端寬表）→ 全部降級成 X、靠 cell 內 \allowbreak 斷。
  if rigid_pt > LINEWIDTH_PT * 0.96 or (nflex == 0 and rigid_pt > LINEWIDTH_PT) then
    -- 依 maxc 權重攤整頁寬（仍偏好寬 token 欄，但夾住極端比例避免窄欄餓死）。
    local sum = 0
    for i = 1, ncol do sum = sum + maxc[i] end
    local f, cs = {}, 0
    for i = 1, ncol do
      f[i] = math.max(0.45, math.min(2.6, maxc[i] * ncol / sum)); cs = cs + f[i]
    end
    local spec = VRULE
    for i = 1, ncol do
      spec = spec .. string.format('>{\\hsize=%.3f\\hsize\\raggedright\\arraybackslash}X', f[i] * ncol / cs) .. VRULE
    end
    return spec, '\\linewidth'
  end

  -- 原子欄總寬上限：別讓原子欄吃光、把散文欄餓死成 1 字。留給散文欄至少 RIGID_CAP 反比。
  -- （CSS 嚴格作法會把 CJK 散文壓到 1 字、保 token 完整；這裡折衷：原子欄超過上限就等比縮，
  --  只有在真的塞不下時才可能讓最長 token 斷一次，一般表不觸發。）
  local RIGID_CAP = LINEWIDTH_PT * (nflex > 0 and 0.66 or 1.0)
  if rigid_pt > RIGID_CAP and rigid_pt > 0 then
    local k = RIGID_CAP / rigid_pt
    for i = 1, ncol do if rigid[i] then want[i] = (want[i] - PAD) * k + PAD end end
    rigid_pt = RIGID_CAP
  end

  -- 一般情形：原子欄 p{固定寬}、散文欄 X 瓜分剩餘寬。
  local natural_total = rigid_pt + flex_max_pt
  local target_pt, tabwidth
  if natural_total <= LINEWIDTH_PT then
    target_pt, tabwidth = natural_total, string.format('%.2fpt', natural_total)   -- 窄表：自然寬靠左
  else
    target_pt, tabwidth = LINEWIDTH_PT, '\\linewidth'                             -- 寬表：鎖頁寬、散文 wrap
  end

  -- 散文欄 X：\hsize 權重 ∝ 各散文欄 maxc（想要越寬的分越多）。tabularx 會把
  -- （目標寬 − 原子 p{} 欄寬）依這些權重分給 X 欄；故只需給「相對」權重、均值=1。
  local flex_sum = 0
  for i = 1, ncol do if not rigid[i] then flex_sum = flex_sum + maxc[i] end end

  local spec = VRULE
  for i = 1, ncol do
    if rigid[i] then
      -- 原子欄：固定 p{}；左對齊、頂對齊；扣掉 2·\tabcolsep 還原為「內容寬」。
      spec = spec .. string.format('>{\\raggedright\\arraybackslash}p{%.2fpt}', want[i] - PAD) .. VRULE
    else
      local share = (flex_sum > 0) and (maxc[i] / flex_sum) or (1 / nflex)
      spec = spec .. string.format('>{\\hsize=%.3f\\hsize\\raggedright\\arraybackslash}X', math.max(0.25, share * nflex)) .. VRULE
    end
  end
  return spec, tabwidth
end

function Table(tbl)
  local ncol = #tbl.colspecs
  if ncol == 0 then return nil end
  -- 所有表格一律鎖在 \linewidth 內，右側保留正常邊距、絕不貼頁緣。
  -- 寬表（>=5 欄）改用 \footnotesize 縮小字級讓欄塞得下，X 欄自動換行；窄表用 \small。
  -- #4 env 一律 xltabular（可跨頁）：寬表若塞不下整塊不再被推到次頁、留下大白洞，
  -- 而是自然跨頁順流。xltabular = tabularx（自動欄寬）+ longtable（可斷頁）合體。
  local wide = ncol >= 5
  local env = 'xltabular'
  -- 字級用顯式 \fontsize（非 \normalsize/\small）：upstream cas-sc 會把 NFSS 字級巨集重設、
  -- \renewcommand 無效，只有顯式 \fontsize 可靠。表格比 14.5pt 正文小：窄表 TBL_NARROW(預設12)、
  -- 寬表 TBL_WIDE(預設11)（也讓寬表少一點硬斷）。baseline 以 12→14.5 / 11→13.5 為錨等比例縮放，
  -- EM 欄寬常數已同步（見 colspec）。預設 size=12 → 與舊硬寫值 byte-identical。
  local o = OPTS
  local function tbl_fs(pt, base) return string.format('\\fontsize{%g}{%g}\\selectfont', pt, base) end
  local fontsize = wide and tbl_fs(o.wide, 13.5 * o.wide / 11)
                         or tbl_fs(o.narrow, 14.5 * o.narrow / 12)
  local spec, tabwidth = colspec(tbl, ncol, wide, o)
  local out = {}
  out[#out + 1] = '\\begingroup'
  -- GitHub 風 cell padding：\tabcolsep（窄表 8pt、寬表 5pt）、\arraystretch 1.6（列高更鬆）。
  out[#out + 1] = fontsize .. '\\setlength{\\tabcolsep}{' .. (wide and '5pt' or '8pt') .. '}\\renewcommand{\\arraystretch}{1.6}'
  -- 細格線：線寬 0.5pt、顏色 docspecRule（#D0D7DE）。直線改走 colspec 的 !{\vrule}（畫在
  -- \rowcolor 底色之上才可見）；橫線 \hline 同寬同色。\arrayrulecolor 出組即還原。
  out[#out + 1] = '\\setlength{\\arrayrulewidth}{0.5pt}\\arrayrulecolor{docspecRule}'
  out[#out + 1] = '\\setlength{\\aboverulesep}{0pt}\\setlength{\\belowrulesep}{0pt}'
  -- 靠左（GitHub 風）：窄表用自然寬時，longtable 預設置中——改 \LTleft=0、\LTright=\fill 讓它
  -- 像 GitHub 一樣靠左、右側留白；滿寬表無 slack、不受影響。
  out[#out + 1] = '\\setlength{\\LTleft}{0pt}\\setlength{\\LTright}{\\fill}'
  -- #2 表格上方對稱留白（下方留白在 \endgroup 後補）
  out[#out + 1] = '\\par\\addvspace{10pt plus 3pt minus 2pt}\\noindent'
  out[#out + 1] = '\\begin{' .. env .. '}{' .. tabwidth .. '}{' .. spec .. '}'
  out[#out + 1] = '\\hline'
  -- header：淺灰底（docspecZebra＝#F6F8FA、與偶數列同色＝GitHub 風）+ 粗體（header_latex 已加）
  for _, row in ipairs(tbl.head.rows) do
    out[#out + 1] = '\\rowcolor{docspecZebra}'
    out[#out + 1] = row_latex(row, true)
    out[#out + 1] = '\\hline'
  end
  -- xltabular 是 longtable 家族：所有表都標 \endhead，讓表頭（含底色與上下細線）在跨頁時於每頁頂重複。
  out[#out + 1] = '\\endhead'
  -- body rows：每列後 \hline 做出全格；偶數列淺灰底（zebra，與表頭同 #F6F8FA）、奇數列白。
  local rownum = 0
  for _, b in ipairs(tbl.bodies) do
    for _, row in ipairs(b.body) do
      rownum = rownum + 1
      if rownum % 2 == 0 then
        out[#out + 1] = '\\rowcolor{docspecZebra}'
      end
      out[#out + 1] = row_latex(row, false)
      out[#out + 1] = '\\hline'
    end
  end
  out[#out + 1] = '\\end{' .. env .. '}'
  out[#out + 1] = '\\endgroup'
  -- #2 表格下方對稱留白：不緊貼下一段
  out[#out + 1] = '\\par\\addvspace{10pt plus 3pt minus 2pt}\\noindent'
  return pandoc.RawBlock('latex', table.concat(out, '\n'))
end

-- #3 prose 行內 code：切成多個淺灰底小段（段間可斷），長路徑（fleet/sc/**/status 等）
-- 能斷在 / _ 邊界、絕不凸出右界；短 code 仍是一塊連續灰底。
-- 注意：表格 cell 內的 Code 由 cell_to_latex 自走 walk 處理（用 \dspxcellcode），不經此處。
function Code(c)
  return pandoc.RawInline('latex', prose_code_segments(c.text))
end

-- ╔══════════════════════════════════════════════════════════════════════╗
-- ║ mermaid 區塊 → 「可見佔位框」（不再 dump 成 3 整頁原始碼）                ║
-- ╠══════════════════════════════════════════════════════════════════════╣
-- 背景：pandoc 不認得 mermaid → 整塊原始碼被當 verbatim 渲出（OCC 有 3 整頁、超醜）。
-- mermaid→TikZ 沒有自動轉換器（翻譯是 agent 的 judgment、每張一次）。所以這裡只把 mermaid
-- 渲成一個「一眼看出待轉譯」的佔位框：淺色框 + 標籤 + \footnotesize 收進原始碼小字。
-- release 迴圈裡 agent 看 proof 發現此框 → 讀框內 mermaid → 寫等價 TikZ raw block 取代之。
-- 其他語言的 code block（有 class 或無 class 的一般 code）一律 return nil → 維持 pandoc
-- 既有行為（Shaded 語法高亮 / verbatim 灰框，由 preamble 接管），絕不被本 handler 攔。
local function is_mermaid(cb)
  for _, cls in ipairs(cb.classes) do
    if cls == 'mermaid' then return true end
  end
  return false
end

-- 把 mermaid 原始碼逐行 escape，組成 fvextra 友善的小字原始碼（保留斷行）。
-- 用 Verbatim 環境（fvextra 已載、preamble 設好 breaklines）讓長行不溢出框外。
local function mermaid_placeholder(src)
  -- Verbatim 內容不需 LaTeX escape（fancyvrb 逐字輸出），但要避免 \end{Verbatim}
  -- 出現在內容裡提前關環境——mermaid 源不會有，保險起見不特別處理（極端情形退化成多框）。
  local out = {}
  out[#out + 1] = '\\par\\addvspace{10pt plus 3pt minus 2pt}\\noindent'
  out[#out + 1] = '\\begin{tcolorbox}[colback=docspecCodeBg,colframe=docspecRule,'
                  .. 'boxrule=0.6pt,arc=3pt,left=8pt,right=8pt,top=6pt,bottom=6pt]'
  out[#out + 1] = '{\\footnotesize\\sffamily\\bfseries\\color{docspecCodeRule}'
                  .. '\\hspace*{0pt}$\\square$\\,Mermaid 圖（release 時由 agent 轉 TikZ）\\par}'
  out[#out + 1] = '\\vspace{4pt}'
  out[#out + 1] = '\\begin{Verbatim}[fontsize=\\scriptsize,breaklines=true,'
                  .. 'breakanywhere=true,formatcom=\\color{tokComment}]'
  out[#out + 1] = src
  out[#out + 1] = '\\end{Verbatim}'
  out[#out + 1] = '\\end{tcolorbox}'
  out[#out + 1] = '\\par\\addvspace{10pt plus 3pt minus 2pt}\\noindent'
  return table.concat(out, '\n')
end

-- mermaid code block → 佔位框；非 mermaid → nil（不攔，維持 pandoc 既有渲染）。
function CodeBlock(cb)
  if is_mermaid(cb) then
    return pandoc.RawBlock('latex', mermaid_placeholder(cb.text))
  end
  return nil
end

-- 兩段式 filter：第一段只跑 Meta（讀表格旋鈕填 OPTS），第二段才處理 Table/Code/CodeBlock。
-- pandoc 依序套用多個 filter＝保證 Meta 整段先於 Table（單一 filter 內 Meta 反而晚於 Block）。
return {
  { Meta = capture_meta },
  { Table = Table, Code = Code, CodeBlock = CodeBlock },
}
