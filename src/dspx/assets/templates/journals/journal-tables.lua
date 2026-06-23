-- journal-tables.lua — pandoc filter for the docspec journal (emit-only) track.
--
-- pandoc's LaTeX writer renders pipe tables as `longtable`, which the two-column
-- journal classes (IEEEtran [journal], Elsevier cas-dc, IET cta-author) reject with
-- "longtable not in 1-column mode". This filter rewrites each table to a plain
-- `tabular` inside a column-spanning `table*` float, which all of them accept.
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

local function row_tex(row)
  local cells = {}
  for _, c in ipairs(row.cells) do cells[#cells + 1] = cell_text(c) end
  return table.concat(cells, ' & ') .. ' \\\\'
end

function Table(tbl)
  local ncol = #tbl.colspecs
  if ncol == 0 then return nil end
  local cols = string.rep('l', ncol)
  local out = {
    '\\begin{table*}[ht]', '\\centering',
    '\\begin{tabular}{' .. cols .. '}', '\\hline',
  }
  for _, row in ipairs(tbl.head.rows) do out[#out + 1] = row_tex(row) end
  out[#out + 1] = '\\hline'
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do out[#out + 1] = row_tex(row) end
  end
  out[#out + 1] = '\\hline'
  out[#out + 1] = '\\end{tabular}'
  out[#out + 1] = '\\end{table*}'
  return pandoc.RawBlock('latex', table.concat(out, '\n'))
end
