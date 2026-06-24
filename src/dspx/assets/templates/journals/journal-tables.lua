-- journal-tables.lua — pandoc filter for the docspec journal (emit-only) track.
--
-- pandoc's LaTeX writer renders pipe tables as `longtable`, which the two-column
-- journal classes (IEEEtran [journal], Elsevier cas-dc, IET cta-author) reject with
-- "longtable not in 1-column mode". This filter rewrites each table to a
-- `tabularx` inside a column-spanning `table*` float, which all of them accept.
--
-- ★欄型用 tabularx `X`（等分、**自動換行、收進 \textwidth 不溢出**），不是 `l`（自然寬、不換行
--   → 寬表衝出版面）。X 欄設 ragged-right（窄欄不被 justify 拉開大字距）。需要 \usepackage{tabularx}
--   （已在三個 adapter 的 template.tex preamble 加）。
--
-- Cells are flattened to text (pandoc.utils.stringify) with the LaTeX specials
-- escaped — adequate for the journal spike; rich inline markup inside cells is a
-- known limitation recorded in the change's design.md.

local function esc(s)
  s = s:gsub('\\', '\\textbackslash{}')
  s = s:gsub('([&%%#_${}])', '\\%1')
  s = s:gsub('~', '\\textasciitilde{}')
  s = s:gsub('%^', '\\textasciicircum{}')
  return s
end

local function cell_text(cell)
  return esc(pandoc.utils.stringify(cell.contents or cell))
end

local function row_tex(row, bold)
  local cells = {}
  for _, c in ipairs(row.cells) do
    local t = cell_text(c)
    if bold then t = '\\textbf{' .. t .. '}' end
    cells[#cells + 1] = t
  end
  return table.concat(cells, ' & ') .. ' \\\\'
end

function Table(tbl)
  local ncol = #tbl.colspecs
  if ncol == 0 then return nil end
  -- tabularx X 欄＝等分、自動換行、收進 \textwidth（兩欄寬）；ragged-right 避免窄欄 justify 大字距。
  local cols = string.rep('>{\\raggedright\\arraybackslash}X', ncol)
  local out = {
    '\\begin{table*}[ht]', '\\centering',
    '\\begin{tabularx}{\\textwidth}{' .. cols .. '}', '\\hline',
  }
  for _, row in ipairs(tbl.head.rows) do out[#out + 1] = row_tex(row, true) end
  out[#out + 1] = '\\hline'
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do out[#out + 1] = row_tex(row, false) end
  end
  out[#out + 1] = '\\hline'
  out[#out + 1] = '\\end{tabularx}'
  out[#out + 1] = '\\end{table*}'
  return pandoc.RawBlock('latex', table.concat(out, '\n'))
end
