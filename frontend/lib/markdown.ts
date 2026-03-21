export function normalizeMarkdown(input: string): string {
  let text = input || ''

  // Ensure headings are followed by a blank line.
  text = text.replace(/^(#{1,6}\s[^\n]+)(\n(?!\n)|$)/gm, '$1\n\n')

  // Ensure tables start on their own line.
  text = text.replace(/(\S)\s(\|[^\n]+\|)/g, '$1\n\n$2')

  // Add blank line before list items if missing.
  text = text.replace(/(\S)\n([*-]\s)/g, '$1\n\n$2')
  text = text.replace(/(\S)\n(\d+\.\s)/g, '$1\n\n$2')

  return text
}
