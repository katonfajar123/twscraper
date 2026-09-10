param(
    [string]$SourceCsv = "..\..\output\MBG_Dataset_DirectReplies_20260907_0825.csv",
    [string]$OutputXlsx = "..\data\annotation_pilot_300_v1.xlsx",
    [string]$AuditJson = "..\data\annotation_pilot_300_v1.audit.json",
    [string]$PreviewDirectory = "..\reports\annotation_pilot_300_v1_previews"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
function Resolve-FromScript([string]$PathValue) {
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $scriptDirectory $PathValue))
}

$sourcePath = Resolve-FromScript $SourceCsv
$outputPath = Resolve-FromScript $OutputXlsx
$auditPath = Resolve-FromScript $AuditJson
$previewPath = Resolve-FromScript $PreviewDirectory

if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "Source CSV tidak ditemukan: $sourcePath"
}
if (Test-Path -LiteralPath $outputPath) {
    throw "Output sudah ada dan tidak akan ditimpa: $outputPath"
}

$outputDirectory = Split-Path -Parent $outputPath
$auditDirectory = Split-Path -Parent $auditPath
foreach ($directory in @($outputDirectory, $auditDirectory, $previewPath)) {
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
}

$seed = 20260907
$labelGuideVersion = "1.0"
$targetPerStratum = 60
$stratumOrder = @(
    "Distribusi_Signal",
    "Overlap",
    "Mutu_Gizi_Signal",
    "Tata_Kelola_Signal",
    "No_Signal"
)

$mutuPattern = '(?i)\b(porsi|gizi|nutrisi|protein|kalori|karbohidrat|karbo|sayur|buah|lauk|menu|rasa|hambar|asin|manis|enak|kenyang|basi|busuk|berjamur|keracunan|mual|diare|higienis|higiene|sanitasi|kontaminasi|kedaluwarsa|kadaluarsa)\b'
$tataPattern = '(?i)\b(vendor|mitra|dapur|sppg|bgn|anggaran|dana|biaya|korupsi|mark[ -]?up|audit|transparansi|akuntabilitas|sop|sertifikat|sertifikasi|inspeksi|pengaduan|aduan|dilaporkan|laporan|tindak lanjut|ditindaklanjuti|evaluasi)\b'
$distribusiPattern = '(?i)\b(distribusi|logistik|kurir|pengiriman|dikirim|terlambat|telat|jadwal|rantai pasok|dibagi|pembagian|dibagikan|paket|kemasan|kotak|bocor|tumpah|jangkauan|terjangkau|pelosok|perbatasan|tertinggal|terluar|3t|kebagian)\b'

function Get-CandidateStratum([string]$TextValue) {
    $text = if ($null -eq $TextValue) { "" } else { $TextValue }
    $mutu = [regex]::IsMatch($text, $mutuPattern)
    $tata = [regex]::IsMatch($text, $tataPattern)
    $distribusi = [regex]::IsMatch($text, $distribusiPattern)
    $hitCount = @($mutu, $tata, $distribusi | Where-Object { $_ }).Count
    if ($hitCount -gt 1) { return "Overlap" }
    if ($mutu) { return "Mutu_Gizi_Signal" }
    if ($tata) { return "Tata_Kelola_Signal" }
    if ($distribusi) { return "Distribusi_Signal" }
    return "No_Signal"
}

function Shuffle-Items([object[]]$Items, [System.Random]$Random) {
    $copy = [object[]]$Items.Clone()
    for ($index = $copy.Length - 1; $index -gt 0; $index--) {
        $swapIndex = $Random.Next($index + 1)
        $temporary = $copy[$index]
        $copy[$index] = $copy[$swapIndex]
        $copy[$swapIndex] = $temporary
    }
    return $copy
}

function Get-SafeExcelText([string]$TextValue) {
    if ($null -eq $TextValue) { return "" }
    if ($TextValue -match '^[=+\-@]') { return "'" + $TextValue }
    return $TextValue
}

$sourceHashBefore = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$allRows = @(Import-Csv -LiteralPath $sourcePath)
Write-Host "STAGE source_loaded rows=$($allRows.Count)"
if ($allRows.Count -ne 20000) {
    throw "Dataset sumber diharapkan 20.000 baris, ditemukan $($allRows.Count)."
}

$rootTextById = @{}
foreach ($row in $allRows) {
    if ($row.Hierarki_Komentar -eq "Root_Tweet") {
        $rootId = [string]$row.Tweet_ID
        if (-not $rootTextById.ContainsKey($rootId)) {
            $rootTextById[$rootId] = [string]$row.Teks_Komentar
        }
    }
}
Write-Host "STAGE root_indexed roots=$($rootTextById.Count)"

$eligibleRows = [System.Collections.Generic.List[object]]::new()
$missingRootContext = 0
foreach ($row in $allRows) {
    if ($row.Hierarki_Komentar -ne "Direct_Reply") { continue }
    $tweetId = [string]$row.Tweet_ID
    $rootId = [string]$row.Root_Tweet_ID
    $replyText = [string]$row.Teks_Komentar
    if ([string]::IsNullOrWhiteSpace($tweetId) -or
        [string]::IsNullOrWhiteSpace($rootId) -or
        [string]::IsNullOrWhiteSpace($replyText) -or
        -not $rootTextById.ContainsKey($rootId) -or
        [string]::IsNullOrWhiteSpace([string]$rootTextById[$rootId])) {
        $missingRootContext++
        continue
    }
    $eligibleRows.Add([pscustomobject]@{
        Tweet_ID = $tweetId
        Root_Tweet_ID = $rootId
        Teks_Root = [string]$rootTextById[$rootId]
        Teks_Komentar = $replyText
        Candidate_Stratum = Get-CandidateStratum $replyText
    })
}
Write-Host "STAGE eligible_classified rows=$($eligibleRows.Count)"

$eligibleIdSet = [System.Collections.Generic.HashSet[string]]::new()
foreach ($eligibleRow in $eligibleRows) {
    if (-not $eligibleIdSet.Add([string]$eligibleRow.Tweet_ID)) {
        throw "Direct reply eligible mengandung Tweet_ID duplikat: $($eligibleRow.Tweet_ID)"
    }
}
if ($eligibleIdSet.Count -ne $eligibleRows.Count) {
    throw "Direct reply eligible mengandung Tweet_ID duplikat."
}
Write-Host "STAGE eligible_unique ids=$($eligibleIdSet.Count)"

$rng = [System.Random]::new($seed)
$selected = [System.Collections.Generic.List[object]]::new()
$selectedIds = [System.Collections.Generic.HashSet[string]]::new()
$selectedPerRoot = @{}

foreach ($stratum in $stratumOrder) {
    $candidates = @($eligibleRows | Where-Object { $_.Candidate_Stratum -eq $stratum })
    if ($candidates.Count -lt $targetPerStratum) {
        throw "Stratum $stratum hanya memiliki $($candidates.Count) kandidat."
    }

    $groups = @()
    foreach ($group in ($candidates | Group-Object Root_Tweet_ID)) {
        $groups += [pscustomobject]@{
            RootId = [string]$group.Name
            Rows = @(Shuffle-Items @($group.Group) $rng)
            NextIndex = 0
        }
    }
    $groups = @(Shuffle-Items $groups $rng)
    $stratumSelected = 0

    foreach ($rootCap in @(3, 4, 5, 300)) {
        do {
            $madeProgress = $false
            foreach ($group in $groups) {
                if ($stratumSelected -ge $targetPerStratum) { break }
                $rootId = $group.RootId
                $rootCount = if ($selectedPerRoot.ContainsKey($rootId)) { [int]$selectedPerRoot[$rootId] } else { 0 }
                if ($rootCount -ge $rootCap) { continue }
                while ($group.NextIndex -lt $group.Rows.Count -and
                       $selectedIds.Contains([string]$group.Rows[$group.NextIndex].Tweet_ID)) {
                    $group.NextIndex++
                }
                if ($group.NextIndex -ge $group.Rows.Count) { continue }
                $candidate = $group.Rows[$group.NextIndex]
                $group.NextIndex++
                if ($selectedIds.Add([string]$candidate.Tweet_ID)) {
                    $selected.Add($candidate)
                    $selectedPerRoot[$rootId] = $rootCount + 1
                    $stratumSelected++
                    $madeProgress = $true
                }
            }
        } while ($madeProgress -and $stratumSelected -lt $targetPerStratum)
        if ($stratumSelected -ge $targetPerStratum) { break }
    }

    if ($stratumSelected -ne $targetPerStratum) {
        throw "Gagal mengambil $targetPerStratum sampel untuk $stratum; terpilih $stratumSelected."
    }
    Write-Host "STAGE sampled stratum=$stratum count=$stratumSelected"
}

$sample = @(Shuffle-Items @($selected) $rng)
if ($sample.Count -ne 300) { throw "Pilot harus 300 baris; ditemukan $($sample.Count)." }
if (@($sample | Select-Object -ExpandProperty Tweet_ID -Unique).Count -ne 300) {
    throw "Pilot mengandung Tweet_ID duplikat."
}

$sampleRootCounts = @($sample | Group-Object Root_Tweet_ID | Sort-Object Count -Descending)
$sampleStrata = [ordered]@{}
foreach ($stratum in $stratumOrder) {
    $sampleStrata[$stratum] = @($sample | Where-Object Candidate_Stratum -eq $stratum).Count
}
Write-Host "STAGE sample_ready rows=$($sample.Count) roots=$($sampleRootCounts.Count)"

$temporarySampleCsv = Join-Path ([System.IO.Path]::GetTempPath()) ("nbmodels_pilot_" + [guid]::NewGuid().ToString("N") + ".csv")
$sample | Select-Object @{Name="No";Expression={0}}, Tweet_ID, Root_Tweet_ID, Teks_Root, Teks_Komentar |
    ForEach-Object -Begin { $rowNumber = 0 } -Process {
        $rowNumber++
        $_.No = $rowNumber
        $_
    } | Export-Csv -LiteralPath $temporarySampleCsv -NoTypeInformation -Encoding UTF8

$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    Write-Host "STAGE excel_started version=$($excel.Version)"
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.ScreenUpdating = $false
    $excel.EnableEvents = $false

    $workbook = $excel.Workbooks.Add()
    $excel.Calculation = -4135
    while ($workbook.Worksheets.Count -gt 1) {
        $workbook.Worksheets.Item($workbook.Worksheets.Count).Delete()
    }
    $guideSheet = $workbook.Worksheets.Item(1)
    $guideSheet.Name = "Petunjuk"
    $summarySheet = $workbook.Worksheets.Add()
    $summarySheet.Name = "Ringkasan"
    $annotator1Sheet = $workbook.Worksheets.Add()
    $annotator1Sheet.Name = "Annotator_1"
    $annotator2Sheet = $workbook.Worksheets.Add()
    $annotator2Sheet.Name = "Annotator_2"
    $adjudicationSheet = $workbook.Worksheets.Add()
    $adjudicationSheet.Name = "Adjudikasi"
    $validationSheet = $workbook.Worksheets.Add()
    $validationSheet.Name = "Validasi"
    Write-Host "STAGE sheets_created"

    $navy = 0x56341F
    $blue = 0xCFAF5B
    $lightBlue = 0xF4E7D8
    $lightGray = 0xF3F4F6
    $darkText = 0x332D29
    $green = 0xD9EAD3
    $amber = 0xD9EAF7
    $red = 0xCECBFF
    $white = 0xFFFFFF

    foreach ($sheet in @($guideSheet, $summarySheet, $annotator1Sheet, $annotator2Sheet, $adjudicationSheet, $validationSheet)) {
        $sheet.Cells.Font.Name = "Aptos"
        $sheet.Cells.Font.Size = 10
        $sheet.Activate()
        $excel.ActiveWindow.DisplayGridlines = $false
    }

    $validationData = @(
        @("Kategori", "Subkategori", "Status", "Kategori_Subkategori"),
        @("Mutu_Gizi", "Kecukupan_Porsi_dan_Nutrisi", "LABELED", "Mutu_Gizi"),
        @("Tata_Kelola", "Variasi_dan_Rasa_Menu", "UNCLEAR", "Mutu_Gizi"),
        @("Distribusi", "Keamanan_Konsumsi", "", "Mutu_Gizi"),
        @("", "Standardisasi_Vendor_dan_Dapur", "", "Tata_Kelola"),
        @("", "Transparansi_dan_Efisiensi_Anggaran", "", "Tata_Kelola"),
        @("", "Responsivitas_Aduan", "", "Tata_Kelola"),
        @("", "Ketepatan_Waktu_Logistik", "", "Distribusi"),
        @("", "Pemerataan_Jangkauan_3T", "", "Distribusi"),
        @("", "Kondisi_Fisik_dan_Pembagian", "", "Distribusi")
    )
    for ($rowIndex = 0; $rowIndex -lt $validationData.Count; $rowIndex++) {
        for ($columnIndex = 0; $columnIndex -lt 4; $columnIndex++) {
            $validationSheet.Cells.Item($rowIndex + 1, $columnIndex + 1).Value2 = $validationData[$rowIndex][$columnIndex]
        }
    }
    $validationSheet.Range("A1:D1").Font.Bold = $true
    $validationSheet.Columns("A:D").AutoFit() | Out-Null
    $workbook.Names.Add("DaftarKategori", "=Validasi!`$A`$2:`$A`$4") | Out-Null
    $workbook.Names.Add("DaftarSubkategori", "=Validasi!`$B`$2:`$B`$10") | Out-Null
    $workbook.Names.Add("DaftarStatus", "=Validasi!`$C`$2:`$C`$3") | Out-Null
    Write-Host "STAGE validation_ready"

    $guideSheet.Range("A1:H1").Merge()
    $guideSheet.Range("A1").Value2 = "PILOT ANOTASI ASPEK MBG - 300 DIRECT REPLY"
    $guideSheet.Range("A1:H1").Interior.Color = $navy
    $guideSheet.Range("A1:H1").Font.Color = $white
    $guideSheet.Range("A1:H1").Font.Bold = $true
    $guideSheet.Range("A1:H1").Font.Size = 18
    $guideSheet.Range("A1:H1").HorizontalAlignment = -4108
    $guideSheet.Range("A1:H1").RowHeight = 32
    $guideSheet.Range("A2:H2").Merge()
    $guideSheet.Range("A2").Value2 = "Versi panduan 1.0 | Dua annotator independen | Candidate strata tidak ditampilkan"
    $guideSheet.Range("A2:H2").Interior.Color = $lightBlue
    $guideSheet.Range("A2:H2").Font.Color = $darkText
    $guideSheet.Range("A2:H2").HorizontalAlignment = -4108

    $guideRows = @(
        @("A4", "ALUR KERJA", $blue, $white),
        @("A5", "1", $lightBlue, $darkText),
        @("B5", "Baca reply, lalu root. Tentukan sasaran utama klaim, bukan satu keyword.", $white, $darkText),
        @("A6", "2", $lightBlue, $darkText),
        @("B6", "Isi Kategori_Utama + Subkategori_Primer + status LABELED. Gunakan UNCLEAR jika makna tetap tidak pasti.", $white, $darkText),
        @("A7", "3", $lightBlue, $darkText),
        @("B7", "Annotator 1 dan 2 bekerja terpisah. Jangan melihat label pihak lain sebelum adjudikasi.", $white, $darkText),
        @("A8", "4", $lightBlue, $darkText),
        @("B8", "Reviewer menyelesaikan semua BEDA/UNCLEAR di lembar Adjudikasi tanpa menghapus label asli.", $white, $darkText),
        @("A10", "TIGA KATEGORI UTAMA", $blue, $white),
        @("A11", "Mutu_Gizi", $lightBlue, $darkText),
        @("B11", "Isi, porsi/nutrisi, variasi/rasa, dan keamanan makanan bagi penerima.", $white, $darkText),
        @("A12", "Tata_Kelola", $lightBlue, $darkText),
        @("B12", "Vendor/dapur, standar, anggaran, pengawasan, pengaduan, dan tindak lanjut.", $white, $darkText),
        @("A13", "Distribusi", $lightBlue, $darkText),
        @("B13", "Waktu pengiriman, jangkauan 3T, kondisi paket, dan proses pembagian.", $white, $darkText),
        @("A15", "ATURAN STATUS", $blue, $white),
        @("A16", "LABELED", $green, $darkText),
        @("B16", "Kategori dan subkategori jelas serta konsisten.", $white, $darkText),
        @("A17", "UNCLEAR", $amber, $darkText),
        @("B17", "Kosongkan kategori/subkategori dan tulis alasan; ini bukan kelas keempat.", $white, $darkText),
        @("A19", "KONTROL MUTU", $blue, $white),
        @("B20", "Target Cohen's kappa label utama minimal 0,80. Semua perbedaan wajib di-adjudicate.", $white, $darkText),
        @("B21", "Jangan ubah ID atau teks sumber. Jangan gunakan keyword/prediksi sebagai label.", $white, $darkText),
        @("B22", "Panduan lengkap: NB-Models/LABELING_GUIDE.md", $white, $darkText)
    )
    foreach ($entry in $guideRows) {
        $cell = $guideSheet.Range($entry[0])
        $cell.Value2 = $entry[1]
        $cell.Interior.Color = $entry[2]
        $cell.Font.Color = $entry[3]
        if ($entry[0] -in @("A4", "A10", "A15", "A19")) {
            $guideSheet.Range($entry[0] + ":H" + $cell.Row).Merge()
            $guideSheet.Range($entry[0] + ":H" + $cell.Row).Font.Bold = $true
        }
    }
    foreach ($rowNumber in @(5, 6, 7, 8, 11, 12, 13, 16, 17, 20, 21, 22)) {
        $guideSheet.Range("B$rowNumber:H$rowNumber").Merge()
        $guideSheet.Range("B$rowNumber:H$rowNumber").WrapText = $true
        $guideSheet.Rows($rowNumber).RowHeight = 30
    }
    $guideSheet.Columns("A").ColumnWidth = 18
    $guideSheet.Columns("B:H").ColumnWidth = 14
    $guideSheet.Range("A4:H22").Borders.Color = 0xDDDDDD
    $guideSheet.Range("A4:H22").Borders.Weight = 2
    Write-Host "STAGE guide_ready"

    $annotationHeaders = @(
        "No", "Tweet_ID", "Root_Tweet_ID", "Teks_Root", "Teks_Komentar",
        "Kategori_Utama", "Subkategori_Primer", "Kategori_Sekunder",
        "Annotation_Status", "Alasan_Singkat", "Annotator_Code",
        "Label_Guide_Version", "QC_Label"
    )

    function Configure-AnnotationSheet($sheet, [string]$title, [string]$tableName) {
        Write-Host "STAGE annotation_begin sheet=$($sheet.Name)"
        $sheet.Range("A1:M1").Merge()
        $sheet.Range("A1").Value2 = $title
        $sheet.Range("A1:M1").Interior.Color = $navy
        $sheet.Range("A1:M1").Font.Color = $white
        $sheet.Range("A1:M1").Font.Bold = $true
        $sheet.Range("A1:M1").Font.Size = 16
        $sheet.Range("A1:M1").RowHeight = 28
        $sheet.Range("A2:M2").Merge()
        $sheet.Range("A2").Value2 = "Kolom A-E adalah sumber terkunci secara prosedural. Isi F-K secara independen; jangan ubah teks/ID."
        $sheet.Range("A2:M2").Interior.Color = $lightBlue
        $sheet.Range("A2:M2").Font.Color = $darkText
        $sheet.Range("A2:M2").WrapText = $true
        for ($columnIndex = 0; $columnIndex -lt $annotationHeaders.Count; $columnIndex++) {
            $sheet.Cells.Item(4, $columnIndex + 1).Value2 = $annotationHeaders[$columnIndex]
        }
        $sheet.Range("A4:M4").Interior.Color = $blue
        $sheet.Range("A4:M4").Font.Color = $white
        $sheet.Range("A4:M4").Font.Bold = $true
        $sheet.Range("A4:M4").WrapText = $true
        $sheet.Range("A4:M4").RowHeight = 34
        $sheet.Range("B5:C304").NumberFormat = "@"
        $sheet.Range("D5:E304").NumberFormat = "@"
        Write-Host "STAGE annotation_headers sheet=$($sheet.Name)"

        $query = $sheet.QueryTables.Add("TEXT;$temporarySampleCsv", $sheet.Range("A4"))
        $query.TextFilePlatform = 65001
        $query.TextFileParseType = 1
        $query.TextFileCommaDelimiter = $true
        $query.TextFileTextQualifier = 1
        $query.TextFileColumnDataTypes = @(1, 2, 2, 2, 2)
        $query.AdjustColumnWidth = $false
        $query.PreserveFormatting = $true
        $query.RefreshStyle = 1
        $query.Refresh($false) | Out-Null
        $query.Delete()
        $sheet.Range("L5:L304").Value2 = $labelGuideVersion
        Write-Host "STAGE annotation_data sheet=$($sheet.Name)"
        $sheet.Range("M5").Formula = '=IF(AND(F5="",G5="",I5=""),"",IF(AND(I5="UNCLEAR",F5="",G5=""),"OK",IF(AND(I5="LABELED",F5<>"",G5<>"",OR(AND(F5="Mutu_Gizi",COUNTIF(Validasi!$B$2:$B$4,G5)>0),AND(F5="Tata_Kelola",COUNTIF(Validasi!$B$5:$B$7,G5)>0),AND(F5="Distribusi",COUNTIF(Validasi!$B$8:$B$10,G5)>0))),"OK","CEK_LABEL")))'
        $sheet.Range("M5:M304").FillDown()
        Write-Host "STAGE annotation_formulas sheet=$($sheet.Name)"

        foreach ($validationSpec in @(
            @("F5:F304", "=DaftarKategori"),
            @("G5:G304", "=DaftarSubkategori"),
            @("H5:H304", "=DaftarKategori"),
            @("I5:I304", "=DaftarStatus")
        )) {
            $range = $sheet.Range($validationSpec[0])
            $range.Validation.Delete()
            $range.Validation.Add(3, 1, 1, $validationSpec[1])
            $range.Validation.IgnoreBlank = $true
            $range.Validation.InCellDropdown = $true
            $range.Validation.ShowError = $true
            $range.Validation.ErrorTitle = "Nilai tidak valid"
            $range.Validation.ErrorMessage = "Pilih nilai dari daftar panduan."
        }
        Write-Host "STAGE annotation_validation sheet=$($sheet.Name)"

        $sheet.Range("F5:M304").Interior.Color = 0xFFFDF5
        $sheet.Range("M5:M304").FormatConditions.Delete()
        $conditionOk = $sheet.Range("M5:M304").FormatConditions.Add(1, 3, '="OK"')
        $conditionOk.Interior.Color = $green
        $conditionCheck = $sheet.Range("M5:M304").FormatConditions.Add(1, 3, '="CEK_LABEL"')
        $conditionCheck.Interior.Color = $red
        Write-Host "STAGE annotation_formatting sheet=$($sheet.Name)"

        $table = $sheet.ListObjects.Add(1, $sheet.Range("A4:M304"), $null, 1)
        $table.Name = $tableName
        $table.TableStyle = "TableStyleMedium2"
        Write-Host "STAGE annotation_table sheet=$($sheet.Name)"
        $sheet.Columns("A").ColumnWidth = 6
        $sheet.Columns("B:C").ColumnWidth = 22
        $sheet.Columns("D:E").ColumnWidth = 42
        $sheet.Columns("F").ColumnWidth = 18
        $sheet.Columns("G").ColumnWidth = 38
        $sheet.Columns("H:I").ColumnWidth = 20
        $sheet.Columns("J").ColumnWidth = 32
        $sheet.Columns("K:M").ColumnWidth = 20
        $sheet.Range("D5:E304").WrapText = $true
        $sheet.Range("A5:C304").HorizontalAlignment = -4108
        $sheet.Range("F5:I304").HorizontalAlignment = -4108
        $sheet.Range("L5:M304").HorizontalAlignment = -4108
        $sheet.Rows("5:304").RowHeight = 48
        $sheet.Activate()
        $excel.ActiveWindow.SplitColumn = 5
        $excel.ActiveWindow.SplitRow = 4
        $excel.ActiveWindow.FreezePanes = $true
        $excel.ActiveWindow.Zoom = 80
        Write-Host "STAGE annotation_end sheet=$($sheet.Name)"
    }

    Configure-AnnotationSheet $annotator1Sheet "LEMBAR ANNOTATOR 1" "TabelAnnotator1"
    Write-Host "STAGE annotator_1_ready"
    Configure-AnnotationSheet $annotator2Sheet "LEMBAR ANNOTATOR 2" "TabelAnnotator2"
    Write-Host "STAGE annotator_2_ready"

    $adjudicationHeaders = @(
        "No", "Tweet_ID", "Root_Tweet_ID", "Teks_Root", "Teks_Komentar",
        "A1_Kategori", "A1_Subkategori", "A1_Status", "A2_Kategori",
        "A2_Subkategori", "A2_Status", "Agreement", "Kategori_Final",
        "Subkategori_Final", "Status_Final", "Catatan_Adjudikasi",
        "Label_Guide_Version"
    )
    $adjudicationSheet.Range("A1:Q1").Merge()
    $adjudicationSheet.Range("A1").Value2 = "ADJUDIKASI PILOT ANOTASI MBG"
    $adjudicationSheet.Range("A1:Q1").Interior.Color = $navy
    $adjudicationSheet.Range("A1:Q1").Font.Color = $white
    $adjudicationSheet.Range("A1:Q1").Font.Bold = $true
    $adjudicationSheet.Range("A1:Q1").Font.Size = 16
    $adjudicationSheet.Range("A2:Q2").Merge()
    $adjudicationSheet.Range("A2").Value2 = "Kolom F-L mengambil keputusan asli otomatis. Isi M, N, dan P hanya untuk kasus BEDA/UNCLEAR."
    $adjudicationSheet.Range("A2:Q2").Interior.Color = $lightBlue
    for ($columnIndex = 0; $columnIndex -lt $adjudicationHeaders.Count; $columnIndex++) {
        $adjudicationSheet.Cells.Item(4, $columnIndex + 1).Value2 = $adjudicationHeaders[$columnIndex]
    }
    $adjudicationSheet.Range("A4:Q4").Interior.Color = $blue
    $adjudicationSheet.Range("A4:Q4").Font.Color = $white
    $adjudicationSheet.Range("A4:Q4").Font.Bold = $true
    $adjudicationSheet.Range("A4:Q4").WrapText = $true
    $adjudicationSheet.Range("B5:C304").NumberFormat = "@"
    $adjudicationQuery = $adjudicationSheet.QueryTables.Add("TEXT;$temporarySampleCsv", $adjudicationSheet.Range("A4"))
    $adjudicationQuery.TextFilePlatform = 65001
    $adjudicationQuery.TextFileParseType = 1
    $adjudicationQuery.TextFileCommaDelimiter = $true
    $adjudicationQuery.TextFileTextQualifier = 1
    $adjudicationQuery.TextFileColumnDataTypes = @(1, 2, 2, 2, 2)
    $adjudicationQuery.AdjustColumnWidth = $false
    $adjudicationQuery.PreserveFormatting = $true
    $adjudicationQuery.RefreshStyle = 1
    $adjudicationQuery.Refresh($false) | Out-Null
    $adjudicationQuery.Delete()
    $adjudicationSheet.Range("Q5:Q304").Value2 = $labelGuideVersion
    $adjudicationSheet.Range("F5").Formula = "='Annotator_1'!F5"
    $adjudicationSheet.Range("G5").Formula = "='Annotator_1'!G5"
    $adjudicationSheet.Range("H5").Formula = "='Annotator_1'!I5"
    $adjudicationSheet.Range("I5").Formula = "='Annotator_2'!F5"
    $adjudicationSheet.Range("J5").Formula = "='Annotator_2'!G5"
    $adjudicationSheet.Range("K5").Formula = "='Annotator_2'!I5"
    foreach ($column in @("F", "G", "H", "I", "J", "K")) {
        $adjudicationSheet.Range("${column}5:${column}304").FillDown()
    }
    $adjudicationSheet.Range("L5").Formula = '=IF(OR(H5="",K5=""),"BELUM_LENGKAP",IF(AND(F5=I5,G5=J5,H5=K5),"SETUJU","BEDA"))'
    $adjudicationSheet.Range("L5:L304").FillDown()
    $adjudicationSheet.Range("M5").Formula = '=IF(AND(L5="SETUJU",H5="LABELED"),F5,"")'
    $adjudicationSheet.Range("M5:M304").FillDown()
    $adjudicationSheet.Range("N5").Formula = '=IF(AND(L5="SETUJU",H5="LABELED"),G5,"")'
    $adjudicationSheet.Range("N5:N304").FillDown()
    $adjudicationSheet.Range("O5").Formula = '=IF(L5="BELUM_LENGKAP","BELUM_LENGKAP",IF(AND(L5="SETUJU",H5="LABELED"),"SIAP",IF(AND(L5="SETUJU",H5="UNCLEAR"),"UNCLEAR",IF(M5<>"","ADJUDICATED","REVIEW"))))'
    $adjudicationSheet.Range("O5:O304").FillDown()
    foreach ($validationSpec in @(
        @("M5:M304", "=DaftarKategori"),
        @("N5:N304", "=DaftarSubkategori")
    )) {
        $range = $adjudicationSheet.Range($validationSpec[0])
        $range.Validation.Delete()
        $range.Validation.Add(3, 1, 1, $validationSpec[1])
        $range.Validation.IgnoreBlank = $true
        $range.Validation.InCellDropdown = $true
        $range.Validation.ShowError = $true
    }
    $adjudicationSheet.Range("L5:L304").FormatConditions.Delete()
    $conditionDifferent = $adjudicationSheet.Range("L5:L304").FormatConditions.Add(1, 3, '="BEDA"')
    $conditionDifferent.Interior.Color = $red
    $conditionAgree = $adjudicationSheet.Range("L5:L304").FormatConditions.Add(1, 3, '="SETUJU"')
    $conditionAgree.Interior.Color = $green
    $adjudicationTable = $adjudicationSheet.ListObjects.Add(1, $adjudicationSheet.Range("A4:Q304"), $null, 1)
    $adjudicationTable.Name = "TabelAdjudikasi"
    $adjudicationTable.TableStyle = "TableStyleMedium2"
    $adjudicationSheet.Columns("A").ColumnWidth = 6
    $adjudicationSheet.Columns("B:C").ColumnWidth = 22
    $adjudicationSheet.Columns("D:E").ColumnWidth = 38
    $adjudicationSheet.Columns("F:O").ColumnWidth = 22
    $adjudicationSheet.Columns("P").ColumnWidth = 34
    $adjudicationSheet.Columns("Q").ColumnWidth = 18
    $adjudicationSheet.Range("D5:E304").WrapText = $true
    $adjudicationSheet.Rows("5:304").RowHeight = 48
    $adjudicationSheet.Activate()
    $excel.ActiveWindow.SplitColumn = 5
    $excel.ActiveWindow.SplitRow = 4
    $excel.ActiveWindow.FreezePanes = $true
    $excel.ActiveWindow.Zoom = 75
    Write-Host "STAGE adjudication_ready"

    $summarySheet.Range("A1:M1").Merge()
    $summarySheet.Range("A1").Value2 = "RINGKASAN QC PILOT ANOTASI MBG"
    $summarySheet.Range("A1:M1").Interior.Color = $navy
    $summarySheet.Range("A1:M1").Font.Color = $white
    $summarySheet.Range("A1:M1").Font.Bold = $true
    $summarySheet.Range("A1:M1").Font.Size = 18
    $summarySheet.Range("A3:D3").Merge()
    $summarySheet.Range("A3").Value2 = "Provenance sampel"
    $summarySheet.Range("A3:D3").Interior.Color = $blue
    $summarySheet.Range("A3:D3").Font.Color = $white
    $summarySheet.Range("A4").Value2 = "File sumber"
    $summarySheet.Range("B4:D4").Merge()
    $summarySheet.Range("B4").Value2 = [System.IO.Path]::GetFileName($sourcePath)
    $summarySheet.Range("A5").Value2 = "SHA-256 sumber"
    $summarySheet.Range("B5:D5").Merge()
    $summarySheet.Range("B5").Value2 = $sourceHashBefore
    $summarySheet.Range("A6").Value2 = "Seed"
    $summarySheet.Range("B6").Value2 = $seed
    $summarySheet.Range("A7").Value2 = "Total sampel"
    $summarySheet.Range("B7").Value2 = 300
    $summarySheet.Range("A8").Value2 = "Root unik"
    $summarySheet.Range("B8").Value2 = $sampleRootCounts.Count
    $summarySheet.Range("A9").Value2 = "Maks. sampel/root"
    $summarySheet.Range("B9").Value2 = [int]$sampleRootCounts[0].Count
    Write-Host "STAGE summary_provenance"

    $summarySheet.Range("A11:D11").Merge()
    $summarySheet.Range("A11").Value2 = "Kemajuan dan agreement"
    $summarySheet.Range("A11:D11").Interior.Color = $blue
    $summarySheet.Range("A11:D11").Font.Color = $white
    $summaryMetrics = @(
        @("A12", "Annotator 1 selesai", '=COUNTIF(Annotator_1!$I$5:$I$304,"LABELED")+COUNTIF(Annotator_1!$I$5:$I$304,"UNCLEAR")'),
        @("A13", "Annotator 2 selesai", '=COUNTIF(Annotator_2!$I$5:$I$304,"LABELED")+COUNTIF(Annotator_2!$I$5:$I$304,"UNCLEAR")'),
        @("A14", "Setuju lengkap", '=COUNTIF(Adjudikasi!$L$5:$L$304,"SETUJU")'),
        @("A15", "Berbeda", '=COUNTIF(Adjudikasi!$L$5:$L$304,"BEDA")'),
        @("A16", "Siap/final", '=COUNTIF(Adjudikasi!$O$5:$O$304,"SIAP")+COUNTIF(Adjudikasi!$O$5:$O$304,"ADJUDICATED")')
    )
    foreach ($metric in $summaryMetrics) {
        $summarySheet.Range($metric[0]).Value2 = $metric[1]
        $summarySheet.Range("B" + $summarySheet.Range($metric[0]).Row).Formula = $metric[2]
    }
    Write-Host "STAGE summary_metrics"
    $summarySheet.Range("A18").Value2 = "Metrik agreement"
    $summarySheet.Range("B18").Value2 = "Nilai"
    $summarySheet.Range("A18:D18").Interior.Color = $lightBlue
    $summarySheet.Range("A18:D18").Font.Bold = $true
    $summarySheet.Range("A19").Value2 = "Pasangan label utama lengkap"
    $summarySheet.Range("B19").Formula = '=COUNTIFS(Adjudikasi!$F$5:$F$304,"<>",Adjudikasi!$I$5:$I$304,"<>")'
    $summarySheet.Range("A20").Value2 = "Agreement label utama"
    $summarySheet.Range("B20").Formula = '=SUMPRODUCT(--(Adjudikasi!$F$5:$F$304=Adjudikasi!$I$5:$I$304),--(Adjudikasi!$F$5:$F$304<>""))'

    $summarySheet.Range("A23").Value2 = "Kategori"
    $summarySheet.Range("B23").Value2 = "Annotator 1"
    $summarySheet.Range("C23").Value2 = "Annotator 2"
    $summarySheet.Range("D23").Value2 = "Final"
    $summarySheet.Range("A23:D23").Interior.Color = $blue
    $summarySheet.Range("A23:D23").Font.Color = $white
    $categories = @("Mutu_Gizi", "Tata_Kelola", "Distribusi")
    for ($categoryIndex = 0; $categoryIndex -lt 3; $categoryIndex++) {
        $rowNumber = 24 + $categoryIndex
        $category = $categories[$categoryIndex]
        $summarySheet.Cells.Item($rowNumber, 1).Value2 = $category
        $summarySheet.Cells.Item($rowNumber, 2).Formula = "=COUNTIF(Annotator_1!`$F`$5:`$F`$304,A$rowNumber)"
        $summarySheet.Cells.Item($rowNumber, 3).Formula = "=COUNTIF(Annotator_2!`$F`$5:`$F`$304,A$rowNumber)"
        $summarySheet.Cells.Item($rowNumber, 4).Formula = "=COUNTIF(Adjudikasi!`$M`$5:`$M`$304,A$rowNumber)"
    }
    $summarySheet.Range("A28").Value2 = "Cohen's kappa label utama"
    $summarySheet.Range("B28").Formula = '=IFERROR((B20/B19-SUMPRODUCT(B24:B26,C24:C26)/(B19^2))/(1-SUMPRODUCT(B24:B26,C24:C26)/(B19^2)),"")'
    $summarySheet.Range("B28").NumberFormat = "0.000"
    $summarySheet.Range("A29").Value2 = "Gerbang pilot"
    $summarySheet.Range("B29").Formula = '=IF(B28="","BELUM ADA DATA",IF(B28>=0.8,"LULUS","REVISI PANDUAN"))'
    $summarySheet.Range("A3:D29").Borders.Color = 0xDDDDDD
    $summarySheet.Range("A3:D29").Borders.Weight = 2
    $summarySheet.Columns("A").ColumnWidth = 29
    $summarySheet.Columns("B:D").ColumnWidth = 22
    $summarySheet.Range("B5:D5").Font.Size = 8
    Write-Host "STAGE summary_table"

    $chartObject = $summarySheet.ChartObjects().Add(420, 80, 560, 300)
    $chart = $chartObject.Chart
    $chart.ChartType = 51
    $chart.SetSourceData($summarySheet.Range("A23:D26"))
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = "Distribusi Label - A1, A2, dan Final"
    $chart.HasLegend = $true
    Write-Host "STAGE summary_ready"

    $guideSheet.Move($workbook.Worksheets.Item(1))
    $summarySheet.Move($workbook.Worksheets.Item(2))
    $validationSheet.Visible = 2
    $guideSheet.Activate()
    $excel.ActiveWindow.Zoom = 90
    Write-Host "STAGE workbook_ordered"

    $workbook.BuiltinDocumentProperties("Title").Value = "Pilot Anotasi Aspek MBG 300 Direct Reply"
    $workbook.BuiltinDocumentProperties("Subject").Value = "Ground-truth pilot untuk NB-Models"
    $workbook.BuiltinDocumentProperties("Author").Value = "NB-Models"
    $excel.Calculation = -4105
    $excel.CalculateFull()
    $workbook.SaveAs($outputPath, 51)
    Write-Host "STAGE workbook_saved path=$outputPath"

    function Export-RangePreview($sheet, [string]$rangeAddress, [string]$fileName) {
        $range = $sheet.Range($rangeAddress)
        $sheet.Activate()
        $range.CopyPicture(1, 2)
        $width = [Math]::Min([Math]::Max([double]$range.Width, 800), 2200)
        $height = [Math]::Min([Math]::Max([double]$range.Height, 450), 1400)
        $previewChart = $sheet.ChartObjects().Add(0, 0, $width, $height)
        $previewChart.Chart.Paste() | Out-Null
        $previewChart.Chart.Export((Join-Path $previewPath $fileName), "PNG") | Out-Null
        $previewChart.Delete()
    }

    Export-RangePreview $guideSheet "A1:H22" "01_petunjuk.png"
    Export-RangePreview $summarySheet "A1:M30" "02_ringkasan.png"
    Export-RangePreview $annotator1Sheet "A1:M14" "03_annotator_1.png"
    Export-RangePreview $annotator2Sheet "A1:M14" "04_annotator_2.png"
    Export-RangePreview $adjudicationSheet "A1:Q14" "05_adjudikasi.png"
    $validationSheet.Visible = -1
    Export-RangePreview $validationSheet "A1:D10" "06_validasi.png"
    Write-Host "STAGE previews_exported"
    $validationSheet.Visible = 2
    $guideSheet.Activate()
    $workbook.Save()

    if ($annotator1Sheet.Range("B5").Text -ne [string]$sample[0].Tweet_ID) {
        throw "Tweet_ID tidak tersimpan sebagai string utuh di workbook."
    }
    if ($excel.WorksheetFunction.CountA($annotator1Sheet.Range("F5:K304")) -ne 0 -or
        $excel.WorksheetFunction.CountA($annotator2Sheet.Range("F5:K304")) -ne 0) {
        throw "Kolom label manusia harus kosong pada workbook baru."
    }
    if ($annotator1Sheet.Range("F5").Validation.Type -ne 3 -or
        $annotator1Sheet.Range("I5").Validation.Type -ne 3) {
        throw "Dropdown validasi annotator tidak aktif."
    }
    if ($adjudicationSheet.Range("F5").HasFormula -ne $true -or
        $summarySheet.Range("B28").HasFormula -ne $true) {
        throw "Formula adjudikasi atau kappa tidak tersedia."
    }

    $formulaErrors = [System.Collections.Generic.List[string]]::new()
    foreach ($sheet in @($summarySheet, $annotator1Sheet, $annotator2Sheet, $adjudicationSheet)) {
        try {
            $formulaCells = $sheet.UsedRange.SpecialCells(-4123)
            foreach ($cell in $formulaCells.Cells) {
                if ([string]$cell.Text -match '^#(REF|DIV/0|VALUE|NAME|N/A|NUM|NULL)') {
                    $formulaErrors.Add("$($sheet.Name)!$($cell.Address()): $($cell.Text)")
                }
            }
        } catch {
            # Sheet tanpa formula tidak menghasilkan SpecialCells; aman diabaikan.
        }
    }
    if ($formulaErrors.Count -gt 0) {
        throw "Formula error: $($formulaErrors -join '; ')"
    }
} finally {
    if ($null -ne $workbook) {
        try { $workbook.Close($true) } catch { }
    }
    if ($null -ne $excel) {
        try { $excel.Quit() } catch { }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    if (Test-Path -LiteralPath $temporarySampleCsv) {
        Remove-Item -LiteralPath $temporarySampleCsv -Force
    }
}

$sourceHashAfter = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sourceHashBefore -ne $sourceHashAfter) {
    throw "Hash dataset sumber berubah selama build."
}

$workbookHash = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()
$audit = [ordered]@{
    artifact = [System.IO.Path]::GetFileName($outputPath)
    generated_at_wib = [DateTimeOffset]::Now.ToOffset([TimeSpan]::FromHours(7)).ToString("yyyy-MM-dd HH:mm:ss 'WIB'")
    label_guide_version = $labelGuideVersion
    source_file = [System.IO.Path]::GetFileName($sourcePath)
    source_sha256 = $sourceHashBefore
    source_rows = $allRows.Count
    source_direct_replies = @($allRows | Where-Object Hierarki_Komentar -eq "Direct_Reply").Count
    eligible_direct_replies = $eligibleRows.Count
    excluded_missing_or_empty_root_context = $missingRootContext
    sampling_seed = $seed
    sample_rows = $sample.Count
    unique_tweet_ids = @($sample | Select-Object -ExpandProperty Tweet_ID -Unique).Count
    unique_root_tweet_ids = $sampleRootCounts.Count
    max_rows_per_root = [int]$sampleRootCounts[0].Count
    candidate_strata = $sampleStrata
    human_label_fields_initially_blank = $true
    candidate_strata_exposed_to_annotators = $false
    workbook_sha256 = $workbookHash
    preview_files = @(Get-ChildItem -LiteralPath $previewPath -Filter "*.png" | Sort-Object Name | Select-Object -ExpandProperty Name)
}
$audit | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $auditPath -Encoding UTF8

$audit | ConvertTo-Json -Depth 6
