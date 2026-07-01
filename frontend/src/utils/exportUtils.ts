export const downloadTextFile = (
  filename: string,
  content: string,
  mime: string
) => {
  const blob = new Blob([content], {
    type: mime,
  });

  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');

  a.href = url;
  a.download = filename;

  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  URL.revokeObjectURL(url);
};

export function exportToJSON<T>(data: T, filename: string) {
  downloadTextFile(
    `${filename}_${new Date().toISOString()}.json`,
    JSON.stringify(data, null, 2),
    'application/json'
  );
}

export function exportToCSV<T extends object>(data: T[], filename: string) {
  if (!data || !data.length) return;

  const headers = Object.keys(data[0] as Record<string, unknown>);

  const csvContent = [
    headers.join(','),
    ...data.map((row) =>
      headers
        .map((header) => {
          const cell = (row as Record<string, unknown>)[header];
          if (cell === null || cell === undefined) return '';
          if (typeof cell === 'object') return `"${JSON.stringify(cell).replace(/"/g, '""')}"`;
          const cellStr = String(cell);
          return cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')
            ? `"${cellStr.replace(/"/g, '""')}"`
            : cellStr;
        })
        .join(',')
    ),
  ].join('\n');

  downloadTextFile(
    `${filename}_${new Date().toISOString()}.csv`,
    csvContent,
    'text/csv;charset=utf-8;'
  );
}
