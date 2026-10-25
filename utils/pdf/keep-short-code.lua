-- Adapted from bsu-special-data-structures-en/materials/keep-short-code.lua.
-- Keep short Python listings on one page without changing the Markdown source.
function CodeBlock(block)
  if not FORMAT:match('latex') then
    return nil
  end
  local lines = 1
  for _ in block.text:gmatch('\n') do
    lines = lines + 1
  end
  if lines > 20 then
    return nil
  end
  return {
    pandoc.RawBlock('latex', '\\begin{samepage}'),
    block,
    pandoc.RawBlock('latex', '\\end{samepage}'),
  }
end

-- Leave room for a heading and a short block underneath at every nesting depth.
function Header(block)
  if not FORMAT:match('latex') then
    return nil
  end
  local result = {
    pandoc.RawBlock('latex', '\\Needspace{6\\baselineskip}'),
    block,
  }
  -- Explicit marks also cover unnumbered headings. Pandoc handles TeX escaping.
  local chapter = block.classes:includes('handbook-context-chapter')
  local section = block.classes:includes('handbook-context-section')
  if chapter or section then
    local title = pandoc.write(pandoc.Pandoc({pandoc.Plain(block.content)}), 'latex'):gsub('%s+$', '')
    local command = chapter and 'handbookchapter' or 'handbooksection'
    table.insert(result, pandoc.RawBlock('latex', '\\' .. command .. '{' .. title .. '}'))
  end
  return result
end
