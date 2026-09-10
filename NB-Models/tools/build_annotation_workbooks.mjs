// Usage: node build_annotation_workbooks.mjs <workbook_input.json> <new-output-dir>
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [inputPath, outputDir] = process.argv.slice(2);
if (!inputPath || !outputDir) throw new Error('Input JSON and new output directory are required');
const input = JSON.parse(await fs.readFile(inputPath, 'utf8'));
await fs.mkdir(path.dirname(outputDir), { recursive: true });
await fs.mkdir(outputDir); // Refuse overwrite of an existing annotation run.
const palette = { navy: '#14394D', teal: '#176B78', pale: '#EAF3F5', ink: '#243C49', blue: '#124AA2' };
const literal = value => /^[\s]*[=+\-@]/u.test(value) ? `'${value}` : value;

for (const annotator of ['A1', 'A2']) {
  const wb = Workbook.create();
  const guide = wb.worksheets.add('Petunjuk');
  const sheet = wb.worksheets.add('Anotasi');
  const taxonomy = wb.worksheets.add('Taksonomi');
  for (const s of [guide, sheet, taxonomy]) {
    s.showGridLines = false;
    s.getRange('A1:L310').format.font.name = 'Calibri';
    s.getRange('A1:L310').format.font.size = 11;
    s.getRange('A1:L310').format.font.color = palette.ink;
  }
  function title(s, range, text) {
    const r = s.getRange(range); r.merge(); r.values = [[text]];
    r.format = { fill: palette.navy, font: { bold: true, size: 18, color: '#FFFFFF' }, rowHeight: 34, verticalAlignment: 'center' };
  }
  function header(s, range) {
    s.getRange(range).format = { fill: palette.teal, font: { bold: true, color: '#FFFFFF' }, wrapText: true, rowHeight: 32 };
  }
  title(guide, 'A1:F2', `MBG / Pilot anotasi independen ${annotator}`);
  guide.getRange('A:F').format.columnWidthPx = 155;
  const instructions = [
    ['Tujuan', 'Pilih aspek utama komentar: Mutu_Gizi, Tata_Kelola, atau Distribusi. Ini bukan label sentimen.'],
    ['Langkah 1', 'Buka Anotasi. Baca komentar dan konteks root; setiap baris adalah satu direct reply.'],
    ['Langkah 2', 'Isi kolom E–I. Pilih kategori dan subkategori yang konsisten menggunakan dropdown dan Taksonomi.'],
    ['Langkah 3', 'Jika makna dapat diputuskan: LABELED. Jika ambigu/di luar aspek: UNCLEAR, kosongkan kategori dan tulis alasan.'],
    ['Independensi', `Berkas ini khusus ${annotator}. Jangan melihat hasil annotator lain, strata sampling, atau prediksi model.`],
    ['Data sumber', 'Jangan mengubah kolom A–D, J–K. ID disimpan sebagai teks. Teks lengkap dapat dibaca pada formula bar; tinggi baris boleh diperbesar.'],
    ['Validasi', 'Kolom L memeriksa pasangan kategori/subkategori dan status. Semua baris selesai harus berisi OK.'],
    ['Penyerahan', 'Simpan berkas dengan kode A1/A2. Koordinator baru membandingkan hasil setelah kedua anotator selesai.'],
    ['Tahap berikut', 'Hitung agreement dan Cohen\'s kappa; adjudikasi perbedaan dan UNCLEAR sebelum membuat ground truth.'],
    ['Panduan', `LABELING_GUIDE.md versi ${input.label_guide_version}. Ambiguitas tidak boleh dipaksa masuk suatu kategori.`],
    ['Sumber', input.source_file],
    ['SHA-256 sumber', input.source_sha256],
  ];
  instructions.forEach(([label, value], index) => {
    const row = index + 4;
    guide.getRange(`A${row}`).values = [[label]];
    guide.getRange(`A${row}`).format.font.bold = true;
    guide.getRange(`B${row}:F${row}`).merge();
    guide.getRange(`B${row}`).values = [[value]];
    guide.getRange(`A${row}:F${row}`).format.wrapText = true;
    guide.getRange(`A${row}:F${row}`).format.rowHeight = index === 11 ? 35 : 44;
    if (index % 2 === 0) guide.getRange(`A${row}:F${row}`).format.fill = palette.pale;
  });
  const last = input.rows.length + 5;
  guide.getRange('A18:C18').values = [['Jumlah komentar', 'Selesai valid', 'Perlu diperiksa']];
  header(guide, 'A18:C18');
  guide.getRange('A19:C19').formulas = [[
    `=COUNTA(Anotasi!A6:A${last})`,
    `=COUNTIF(Anotasi!L6:L${last},"OK")`,
    `=COUNTIF(Anotasi!L6:L${last},"PERIKSA")`,
  ]];
  guide.getRange('A19:C19').format = { font: { bold: true, size: 18, color: palette.teal }, rowHeight: 32 };

  const taxonomyRows = Object.entries(input.taxonomy).flatMap(([category, subs]) => subs.map(sub => [category, sub]));
  title(taxonomy, 'A1:B2', 'Taksonomi / Panduan 1.0');
  taxonomy.getRange('A4:B4').values = [['Kategori utama', 'Subkategori primer']];
  taxonomy.getRange(`A5:B${4 + taxonomyRows.length}`).values = taxonomyRows;
  taxonomy.getRange('D4:D6').values = Object.keys(input.taxonomy).map(category => [category]);
  taxonomy.getRange('A:A').format.columnWidthPx = 215;
  taxonomy.getRange('B:B').format.columnWidthPx = 440;
  taxonomy.getRange('C:C').format.columnWidthPx = 25;
  taxonomy.getRange('D:D').format.columnWidthPx = 200;
  taxonomy.getRange('D3').values = [['Kategori dropdown']];
  header(taxonomy, 'A4:B4');
  taxonomy.getRange('A5:B13').format.rowHeight = 30;

  title(sheet, 'A1:L2', `Anotasi ${annotator} / ${input.rows.length} direct reply MBG`);
  sheet.getRange('A3:L3').merge();
  sheet.getRange('A3').values = [['Isi E–I secara independen. Baca Taksonomi; pilih UNCLEAR bila tidak pasti. Teks lengkap tersedia pada formula bar.']];
  sheet.getRange('A3:L3').format.rowHeight = 26;
  const columns = ['Tweet_ID', 'Root_Tweet_ID', 'Teks_Root', 'Teks_Komentar',
    'Kategori_Utama', 'Subkategori_Primer', 'Kategori_Sekunder', 'Annotation_Status',
    'Alasan_Singkat', 'Annotator_Code', 'Label_Guide_Version', 'Validasi'];
  sheet.getRange('A5:L5').values = [columns];
  const values = input.rows.map(row => [row.Tweet_ID, row.Root_Tweet_ID,
    literal(row.Teks_Root), literal(row.Teks_Komentar), '', '', '', '', '', annotator, input.label_guide_version, '']);
  sheet.getRange(`A6:K${last}`).setNumberFormat('@');
  sheet.getRange(`A6:L${last}`).values = values;
  sheet.tables.add(`A5:L${last}`, true, `Annotations_${annotator}`);
  header(sheet, 'A5:L5');
  const widths = { A: 185, B: 185, C: 420, D: 420, E: 175, F: 310, G: 175, H: 165, I: 300, J: 125, K: 140, L: 120 };
  for (const [col, width] of Object.entries(widths)) sheet.getRange(`${col}:${col}`).format.columnWidthPx = width;
  sheet.getRange(`A6:L${last}`).format.wrapText = true;
  sheet.getRange(`A6:L${last}`).format.verticalAlignment = 'top';
  sheet.getRange(`A6:L${last}`).format.rowHeight = 145;
  sheet.getRange(`E6:I${last}`).format.fill = '#FFF8E6';
  sheet.getRange(`E6:I${last}`).format.font.color = palette.blue;
  for (const col of ['E', 'G']) sheet.getRange(`${col}6:${col}${last}`).dataValidation = {
    rule: { type: 'list', formula1: 'Taksonomi!$D$4:$D$6' },
  };
  sheet.getRange(`F6:F${last}`).dataValidation = { rule: { type: 'list', formula1: 'Taksonomi!$B$5:$B$13' } };
  sheet.getRange(`H6:H${last}`).dataValidation = { rule: { type: 'list', values: ['LABELED', 'UNCLEAR'] } };
  sheet.getRange(`L6:L${last}`).formulas = input.rows.map((_, i) => {
    const r = i + 6;
    return [`=IF(AND(E${r}="",F${r}="",G${r}="",H${r}="",I${r}=""),"",IF(OR(AND(H${r}="UNCLEAR",E${r}="",F${r}="",G${r}="",I${r}<>""),AND(H${r}="LABELED",COUNTIFS(Taksonomi!$A$5:$A$13,E${r},Taksonomi!$B$5:$B$13,F${r})=1,OR(G${r}="",AND(COUNTIF(Taksonomi!$D$4:$D$6,G${r})=1,G${r}<>E${r})))),"OK","PERIKSA"))`];
  });
  sheet.getRange(`L6:L${last}`).conditionalFormats.addCustom('=L6="PERIKSA"', { fill: '#FCE4D6' });
  sheet.getRange(`L6:L${last}`).conditionalFormats.addCustom('=L6="OK"', { fill: '#DBEFE5' });
  // Public API discovery is limited to this feature; retained for reproducibility.
  sheet.freezePanes.freezeRows(5);

  for (const [s, range] of [[guide, 'A1:F19'], [sheet, 'C5:H7'], [taxonomy, 'A1:D13']]) {
    const preview = await wb.render({ sheetName: s.name, range, scale: 1 });
    await fs.writeFile(path.join(outputDir, `${annotator}_${s.name}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const check = await wb.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A', options: { useRegex: true, maxResults: 10 }, maxChars: 1500 });
  await fs.writeFile(path.join(outputDir, `${annotator}_formula_check.json`), check.ndjson);
  const exported = await SpreadsheetFile.exportXlsx(wb);
  await exported.save(path.join(outputDir, `MBG_Pilot_${annotator}.xlsx`));
  console.log(`Saved ${annotator}: ${input.rows.length} blank annotations; independent workbook.`);
}
