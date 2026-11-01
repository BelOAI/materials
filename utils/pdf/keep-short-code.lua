-- Adapted from bsu-special-data-structures-en/materials/keep-short-code.lua.
-- Keep short Python listings on one page without changing the Markdown source.
function Div(block)
  if not FORMAT:match('latex') then return nil end
  if block.classes:includes('handbook-quiz-prompt') then
    -- Count Unicode characters and separate list items, rather than UTF-8 bytes.
    -- Reserving bytes doubled Russian text estimates and left excessive gaps.
    local lines, complex = 2, false
    local function prose(child)
      lines = lines + math.max(1, math.ceil(utf8.len(pandoc.utils.stringify(child)) / 58))
    end
    pandoc.walk_block(block, {
      Para = prose, Plain = prose,
      CodeBlock = function(child)
        for line in (child.text .. '\n'):gmatch('(.-)\n') do
          lines = lines + math.max(1, math.ceil(utf8.len(line) / 58))
        end
      end,
      Image = function() complex = true end,
      Table = function() complex = true end,
    })
    if lines > 24 or complex then lines = 4 end
    local result = {pandoc.RawBlock('latex', '\\Needspace{' .. lines .. '\\baselineskip}')}
    for _, child in ipairs(block.content) do table.insert(result, child) end
    return result
  end
  if block.classes:includes('handbook-callout') then
    local labels = {important='Важно', warning='Предупреждение', note='Примечание', tip='Совет'}
    local kind = block.attributes.type
    local title = pandoc.write(pandoc.Pandoc({pandoc.Plain({pandoc.Str(block.attributes.title or labels[kind])})}), 'latex'):gsub('%s+$', '')
    local result = {pandoc.RawBlock('latex', '\\begin{handbookcallout}{' .. kind .. '}{' .. title .. '}')}
    for _, child in ipairs(block.content) do table.insert(result, child) end
    table.insert(result, pandoc.RawBlock('latex', '\\end{handbookcallout}'))
    return result
  end
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
  if block.classes:includes('handbook-lesson-opening') then
    required_lines = 10
  end
  local result = {
    pandoc.RawBlock('latex', '\\Needspace{' .. required_lines .. '\\baselineskip}'),
    block,
  }
  if block.classes:includes('handbook-chapter-opening') then
    result[1] = pandoc.RawBlock('latex', '\\handbookopenchapter')
  end
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
