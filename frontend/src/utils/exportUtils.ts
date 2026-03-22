export function exportToJSON(data: any, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}_${new Date().toISOString()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportToCSV(data: any[], filename: string) {
  if (!data || !data.length) return;
  
  // Get headers
  const headers = Object.keys(data[0]);
  
  // Format CSV rows
  const csvContent = [
    headers.join(','), // Header row
    ...data.map(row => 
      headers.map(header => {
        const cell = row[header];
        // Handle complex objects or strings with commas
        if (cell === null || cell === undefined) return '';
        if (typeof cell === 'object') return `"${JSON.stringify(cell).replace(/"/g, '""')}"`;
        const cellStr = String(cell);
        return cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n') 
          ? `"${cellStr.replace(/"/g, '""')}"` 
          : cellStr;
      }).join(',')
    )
  ].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}_${new Date().toISOString()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
