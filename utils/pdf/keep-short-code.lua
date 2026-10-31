-- Adapted from bsu-special-data-structures-en/materials/keep-short-code.lua.
-- Keep short Python listings on one page without changing the Markdown source.
function Div(block)
  if not FORMAT:match('latex') then return nil end
  if block.classes:includes('handbook-caption') then
    local title = pandoc.write(pandoc.Pandoc(block.content), 'latex'):gsub('%s+$', '')
    return pandoc.RawBlock('latex', '\\caption*{' .. title .. '}')
  end
  if block.classes:includes('handbook-figure') then
    local result = {pandoc.RawBlock('latex', '\\begin{figure}[H]\\centering')}
    for _, child in ipairs(block.content) do table.insert(result, child) end
    table.insert(result, pandoc.RawBlock('latex', '\\end{figure}'))
    return result
  end
end

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
  local title_text = pandoc.utils.stringify(block.content)
  local required_lines = 6
  -- Keep a numbered self-check question with its four choices and feedback.
  if title_text:match('^%d+%.') then
    required_lines = 18
  end
  local result = {
    pandoc.RawBlock('latex', '\\Needspace{' .. required_lines .. '\\baselineskip}'),
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
