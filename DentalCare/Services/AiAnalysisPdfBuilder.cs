using System.Globalization;
using System.Text;
using DentalCare.Models;
using DentalCare.ViewModels;

namespace DentalCare.Services
{
    /// <summary>
    /// Builds a professionally styled, multi-page PDF for AI cephalometric analysis reports.
    /// Layout: navy header band → diagnosis panel → measurement table → treatment cards → footer with page numbers.
    /// </summary>
    public static class AiAnalysisPdfBuilder
    {
        // ── Page geometry ────────────────────────────────────────────────────────────
        private const double PageWidth        = 612;
        private const double PageHeight       = 792;
        private const double MarginLeft       = 52;
        private const double MarginRight      = 52;
        private const double ContentWidth     = PageWidth - MarginLeft - MarginRight;
        private const double HeaderBandHeight = 64;
        private const double FooterY          = 34;
        private const double TopContentY      = PageHeight - HeaderBandHeight - 20;  // first usable Y after header

        // ── Typography ───────────────────────────────────────────────────────────────
        private const int FontSizeTitle       = 20;
        private const int FontSizeSubtitle    = 9;
        private const int FontSizeSection     = 10;
        private const int FontSizeBody        = 9;
        private const int FontSizeMuted       = 8;
        private const int FontSizeHighlight   = 10;
        private const int FontSizeTableHeader = 8;
        private const int FontSizeTableBody   = 9;

        // ── Colour palette (PDF DeviceRGB) ────────────────────────────────────────
        //  Navy    #0D1B3E  – header, section labels, primary text
        //  Teal    #0A7FAC  – highlight text, accent rule, section pill bg
        //  Slate   #64748B  – muted / secondary text
        //  Ink     #1E293B  – body text
        //  Fog     #F1F5F9  – alternating table row, panel background
        //  White   #FFFFFF
        //  Amber   #D97706  – warning accent
        //  Green   #047857  – primary treatment badge

        private const string C_NavyRG   = "0.051 0.106 0.243";   // #0D1B3E
        private const string C_TealRG   = "0.039 0.498 0.675";   // #0A7FAC
        private const string C_SlateRG  = "0.392 0.455 0.545";   // #64748B
        private const string C_InkRG    = "0.118 0.161 0.231";   // #1E293B
        private const string C_FogRG    = "0.945 0.961 0.976";   // #F1F5F9
        private const string C_WhiteRG  = "1 1 1";
        private const string C_AmberRG  = "0.851 0.467 0.024";   // #D97706
        private const string C_GreenRG  = "0.016 0.471 0.341";   // #047857
        private const string C_RuleRG   = "0.820 0.851 0.902";   // #D1D9E6 – hairline rules

        // ── Line heights (pts to advance Y after drawing) ────────────────────────
        private const double LH_Body      = 14;
        private const double LH_Section   = 22;   // includes top padding
        private const double LH_Highlight = 15;
        private const double LH_Muted     = 12;
        private const double LH_Blank     = 7;
        private const double LH_Title     = 28;

        // ── Wrap width (chars) ────────────────────────────────────────────────────
        private const int MaxLineChars = 92;

        // ─────────────────────────────────────────────────────────────────────────────
        // Public entry point
        // ─────────────────────────────────────────────────────────────────────────────

        public static byte[] Build(
            Patient patient,
            AiAnalysisReportRequest report,
            string doctorName,
            DateTime generatedAt)
        {
            var blocks  = BuildContentBlocks(patient, report, doctorName, generatedAt);
            var pages   = PaginateBlocks(blocks);
            var overlay = TryReadPngImage(report.OverlayImageBase64);
            return BuildPdf(pages, overlay);
        }

        // ─────────────────────────────────────────────────────────────────────────────
        // Content model
        // ─────────────────────────────────────────────────────────────────────────────

        private enum BlockKind
        {
            Title, Section, Body, Muted, Highlight,
            Blank, Rule, TableHeader, TableRow, TableRowAlt,
            PanelStart, PanelEnd, WarningRow, TreatmentHeader, TreatmentAlt
        }

        private sealed record ContentBlock(string Text, BlockKind Kind, string? SecondaryText = null);

        // ─────────────────────────────────────────────────────────────────────────────
        // Build the logical block list
        // ─────────────────────────────────────────────────────────────────────────────

        private static List<ContentBlock> BuildContentBlocks(
            Patient patient,
            AiAnalysisReportRequest report,
            string doctorName,
            DateTime generatedAt)
        {
            var B = new List<ContentBlock>();

            // ── Report meta ──────────────────────────────────────────────────────
            B.Add(Block("AI Cephalometric Analysis Report", BlockKind.Title));
            B.Add(Block($"Generated {generatedAt:dd MMM yyyy · HH:mm}  ·  Reviewing Clinician: {Safe(doctorName)}  ·  Protocol: {ValueOrDefault(report.ProtocolName, "Core Lateral Screening")} ({ValueOrDefault(report.ProtocolId, "core_lateral")})", BlockKind.Muted));
            B.Add(Block("", BlockKind.Rule));

            // ── Patient information ──────────────────────────────────────────────
            B.Add(SectionBlock("Patient Information"));
            B.Add(Block($"Name: {Safe(patient.Name)}   |   ID: #{patient.Id}   |   Age / Gender: {patient.Age} yrs / {Safe(patient.Gender)}   |   Phone: {Safe(patient.Phone)}" +
                        (string.IsNullOrWhiteSpace(patient.Email) ? "" : $"   |   Email: {Safe(patient.Email)}"), BlockKind.Body));
            B.Add(Block("", BlockKind.Blank));

            B.Add(SectionBlock("Clinical Review"));
            B.Add(Block(report.IsDoctorReviewed
                ? "Status: Doctor reviewed and approved this AI-assisted report."
                : "Status: Draft AI output. Doctor review is required before clinical use.", BlockKind.Body));
            if (!string.IsNullOrWhiteSpace(report.ReviewNotes))
            {
                foreach (var line in WrapText($"Review notes: {Safe(report.ReviewNotes)}", MaxLineChars))
                    B.Add(Block(line, BlockKind.Muted));
            }
            B.Add(Block("", BlockKind.Blank));

            // ── Diagnosis summary panel ──────────────────────────────────────────
            B.Add(SectionBlock("Diagnosis Summary"));
            B.Add(Block("", BlockKind.PanelStart));
            B.Add(Block($"Skeletal Class: {ValueOrDefault(report.SkeletalClass, "Unclassified")}", BlockKind.Highlight, $"Vertical Pattern: {ValueOrDefault(report.VerticalPattern, "Not specified")}"));
            B.Add(Block("", BlockKind.Blank));
            foreach (var line in WrapText(ValueOrDefault(report.Summary, "No clinical summary returned."), MaxLineChars))
                B.Add(Block(line, BlockKind.Body));
            B.Add(Block("", BlockKind.PanelEnd));
            B.Add(Block("", BlockKind.Blank));

            // ── Measurement highlights ───────────────────────────────────────────
            var highlights = BuildMeasurementHighlights(report.MeasurementRows, report.Measurements);
            if (highlights.Count > 0)
            {
                B.Add(SectionBlock("Key Measurement Highlights"));
                foreach (var (label, value) in highlights)
                    B.Add(Block(label, BlockKind.Body, value));
                B.Add(Block("", BlockKind.Blank));
            }

            // ── Warnings ─────────────────────────────────────────────────────────
            if (report.Warnings.Any())
            {
                B.Add(SectionBlock("Clinical Warnings"));
                foreach (var w in report.Warnings)
                    B.Add(Block(Safe(w), BlockKind.WarningRow));
                B.Add(Block("", BlockKind.Blank));
            }

            // ── Measurements table ───────────────────────────────────────────────
            B.Add(SectionBlock("Cephalometric Measurements"));
            if (report.MeasurementRows.Any())
            {
                B.Add(Block("Measurement", BlockKind.TableHeader, "Value|Norm|Diff|Status"));
                var ordered = report.MeasurementRows.OrderBy(m => m.MeasurementName).ToList();
                for (var i = 0; i < ordered.Count; i++)
                {
                    var item  = ordered[i];
                    var unit  = string.IsNullOrWhiteSpace(item.Unit) ? InferMeasurementUnit(item.MeasurementName) : Safe(item.Unit);
                    var name  = Truncate(Safe(item.MeasurementName), 36);
                    var val   = $"{item.Value.ToString("0.0", CultureInfo.InvariantCulture)} {unit}";
                    var norm  = item.NormalValue.HasValue ? item.NormalValue.Value.ToString("0.0", CultureInfo.InvariantCulture) : "N/A";
                    var diff  = item.Difference.HasValue ? item.Difference.Value.ToString("+0.0;-0.0;0.0", CultureInfo.InvariantCulture) : "N/A";
                    var status = NormalizeMeasurementStatus(item.Status, item.Label, item.Difference);
                    var kind  = i % 2 == 0 ? BlockKind.TableRow : BlockKind.TableRowAlt;
                    B.Add(Block(name, kind, $"{val}|{norm}|{diff}|{status}"));
                }
            }
            else if (report.Measurements.Any())
            {
                B.Add(Block("Measurement", BlockKind.TableHeader, "Value|Norm|Diff|Status"));
                var ordered = report.Measurements.OrderBy(m => m.Key).ToList();
                for (var i = 0; i < ordered.Count; i++)
                {
                    var item = ordered[i];
                    var unit = InferMeasurementUnit(item.Key);
                    var name = Truncate(Safe(item.Key), 36);
                    var val = $"{item.Value.ToString("0.0", CultureInfo.InvariantCulture)} {unit}";
                    var kind = i % 2 == 0 ? BlockKind.TableRow : BlockKind.TableRowAlt;
                    B.Add(Block(name, kind, $"{val}|N/A|N/A|Normal"));
                }
            }
            else
            {
                B.Add(Block("No measurements were returned by the analysis engine.", BlockKind.Muted));
            }
            B.Add(Block("", BlockKind.Blank));

            // ── Treatment suggestions ────────────────────────────────────────────
            B.Add(SectionBlock("Treatment Suggestions"));
            if (report.Treatments.Any())
            {
                foreach (var t in report.Treatments)
                {
                    var badge    = t.IsPrimary ? "PRIMARY" : "ALTERNATIVE";
                    var duration = t.DurationMonths > 0 ? $"{t.DurationMonths} months" : "Duration TBD";
                    var header   = $"{ValueOrDefault(t.TreatmentName, "Treatment Option")}  ·  {badge}  ·  {duration}";
                    B.Add(Block(header, t.IsPrimary ? BlockKind.TreatmentHeader : BlockKind.TreatmentAlt));
                    if (!string.IsNullOrWhiteSpace(t.Description))
                        foreach (var line in WrapText($"Description: {Safe(t.Description)}", MaxLineChars))
                            B.Add(Block(line, BlockKind.Body));
                    if (!string.IsNullOrWhiteSpace(t.Rationale))
                        foreach (var line in WrapText($"Rationale: {Safe(t.Rationale)}", MaxLineChars))
                            B.Add(Block(line, BlockKind.Muted));
                    B.Add(Block("", BlockKind.Blank));
                }
            }
            else
            {
                B.Add(Block("No treatment suggestions were returned by the analysis engine.", BlockKind.Muted));
                B.Add(Block("", BlockKind.Blank));
            }

            // ── Disclaimer ───────────────────────────────────────────────────────
            B.Add(Block("", BlockKind.Rule));
            B.Add(Block("Clinical Review Notice", BlockKind.Section));
            B.Add(Block("This report is AI-assisted and must be independently reviewed, validated, and approved by a qualified dental clinician before use in any clinical decision-making.", BlockKind.Muted));

            return B;
        }

        private static ContentBlock Block(string text, BlockKind kind, string? secondary = null)
            => new(text, kind, secondary);

        private static ContentBlock SectionBlock(string text)
            => new(text, BlockKind.Section);

        // ─────────────────────────────────────────────────────────────────────────────
        // Pagination: assign blocks to pages by tracking consumed Y
        // ─────────────────────────────────────────────────────────────────────────────

        private sealed record PageBlocks(List<ContentBlock> Blocks);

        private static List<PageBlocks> PaginateBlocks(List<ContentBlock> blocks)
        {
            var pages   = new List<PageBlocks>();
            var current = new List<ContentBlock>();
            var y       = TopContentY;

            foreach (var block in blocks)
            {
                var h = BlockHeight(block);
                if (y - h < FooterY + 20 && current.Count > 0)
                {
                    pages.Add(new PageBlocks(current));
                    current = new List<ContentBlock>();
                    y       = TopContentY;
                }
                current.Add(block);
                y -= h;
            }

            if (current.Count > 0)
                pages.Add(new PageBlocks(current));

            if (pages.Count == 0)
                pages.Add(new PageBlocks(new List<ContentBlock> { Block("AI Cephalometric Analysis Report", BlockKind.Title) }));

            return pages;
        }

        private static double BlockHeight(ContentBlock b) => b.Kind switch
        {
            BlockKind.Title          => LH_Title,
            BlockKind.Section        => LH_Section + 4,
            BlockKind.Highlight      => LH_Highlight * 2 + 4,
            BlockKind.Muted          => LH_Muted,
            BlockKind.Blank          => LH_Blank,
            BlockKind.Rule           => 10,
            BlockKind.TableHeader    => 18,
            BlockKind.TableRow       => 14,
            BlockKind.TableRowAlt    => 14,
            BlockKind.PanelStart     => 6,
            BlockKind.PanelEnd       => 6,
            BlockKind.WarningRow     => 15,
            BlockKind.TreatmentHeader=> 18,
            BlockKind.TreatmentAlt  => 18,
            _                        => LH_Body,
        };

        // ─────────────────────────────────────────────────────────────────────────────
        // Measurement highlights helper
        // ─────────────────────────────────────────────────────────────────────────────

        private static List<(string Label, string Value)> BuildMeasurementHighlights(
            List<AiMeasurementReportItem> rows,
            Dictionary<string, float> measurements)
        {
            var result = new List<(string, string)>();
            TryAdd("ANB",        "Sagittal Jaw Relationship",    "°");
            TryAdd("SNA",        "Maxillary Position",           "°");
            TryAdd("SNB",        "Mandibular Position",          "°");
            TryAdd("FMA (FH-MP)","Vertical Divergence",          "°");
            TryAdd("SN-GoGn",   "Mandibular Plane Angle",        "°");
            TryAdd("IMPA",      "Lower Incisor Inclination",     "°");
            TryAdd("LAFH",      "Lower Anterior Facial Height",  "mm");
            return result;

            void TryAdd(string key, string label, string unit)
            {
                var row = rows.FirstOrDefault(r => string.Equals(r.MeasurementName, key, StringComparison.OrdinalIgnoreCase));
                if (row != null)
                {
                    var status = NormalizeMeasurementStatus(row.Status, row.Label, row.Difference);
                    var norm = row.NormalValue.HasValue ? $" | norm {row.NormalValue.Value.ToString("0.0", CultureInfo.InvariantCulture)}" : "";
                    var diff = row.Difference.HasValue ? $" | diff {row.Difference.Value.ToString("+0.0;-0.0;0.0", CultureInfo.InvariantCulture)}" : "";
                    result.Add(($"{label} ({key})", $"{row.Value.ToString("0.0", CultureInfo.InvariantCulture)} {ValueOrDefault(row.Unit, unit)}{norm}{diff} | {status}"));
                }
                else if (measurements.TryGetValue(key, out var v))
                {
                    result.Add(($"{label} ({key})", $"{v.ToString("0.0", CultureInfo.InvariantCulture)} {unit}"));
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────────────────
        // PDF binary builder
        // ─────────────────────────────────────────────────────────────────────────────

        private static byte[] BuildPdf(List<PageBlocks> textPages, PngPdfImage? overlay)
        {
            // Build page list: insert overlay as page 2 (after cover page) if present
            var pageList  = new List<(List<ContentBlock>? Blocks, PngPdfImage? Image)>();
            pageList.AddRange(textPages.Select(p => ((List<ContentBlock>?)p.Blocks, (PngPdfImage?)null)));
            if (overlay != null)
                pageList.Insert(Math.Min(1, pageList.Count), (null, overlay));

            var totalPages   = pageList.Count;
            var pageObjStart = 3;
            var fontObjId    = pageObjStart + totalPages * 2;
            var nextObjId    = fontObjId + 1;
            var imageObjId   = overlay != null ? nextObjId++ : 0;

            var objects = new Dictionary<int, byte[]>
            {
                [1] = Ascii("<< /Type /Catalog /Pages 2 0 R >>")
            };

            var kids = new StringBuilder();
            for (var i = 0; i < totalPages; i++)
            {
                var pageObjId    = pageObjStart + i * 2;
                var contentObjId = pageObjId + 1;
                kids.Append($"{pageObjId} 0 R ");

                var imgRes = pageList[i].Image != null
                    ? $"/XObject << /Im1 {imageObjId} 0 R >> "
                    : "";

                objects[pageObjId] = Ascii(
                    $"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {(int)PageWidth} {(int)PageHeight}] " +
                    $"/Resources << /Font << /F1 {fontObjId} 0 R >> {imgRes}>> " +
                    $"/Contents {contentObjId} 0 R >>");

                objects[contentObjId] = pageList[i].Image != null
                    ? BuildOverlayPageStream(pageList[i].Image!)
                    : BuildTextPageStream(pageList[i].Blocks!, i + 1, totalPages);
            }

            objects[2]        = Ascii($"<< /Type /Pages /Kids [{kids}] /Count {totalPages} >>");
            objects[fontObjId] = Ascii("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");

            if (overlay != null)
                objects[imageObjId] = BuildImageObject(overlay);

            // ── Serialise ────────────────────────────────────────────────────────
            using var ms = new MemoryStream();
            WriteAscii(ms, "%PDF-1.4\n");

            var maxObjId = nextObjId - 1;
            var offsets  = new long[maxObjId + 1];

            for (var id = 1; id <= maxObjId; id++)
            {
                offsets[id] = ms.Position;
                WriteAscii(ms, $"{id} 0 obj\n");
                ms.Write(objects[id]);
                WriteAscii(ms, "\nendobj\n");
            }

            var xrefPos = ms.Position;
            WriteAscii(ms, $"xref\n0 {maxObjId + 1}\n");
            WriteAscii(ms, "0000000000 65535 f \n");
            for (var i = 1; i <= maxObjId; i++)
                WriteAscii(ms, $"{offsets[i]:0000000000} 00000 n \n");

            WriteAscii(ms, $"trailer\n<< /Size {maxObjId + 1} /Root 1 0 R >>\nstartxref\n{xrefPos}\n%%EOF");
            return ms.ToArray();
        }

        // ─────────────────────────────────────────────────────────────────────────────
        // Text page stream
        // ─────────────────────────────────────────────────────────────────────────────

        private static byte[] BuildTextPageStream(List<ContentBlock> blocks, int pageNum, int totalPages)
        {
            var s = new StringBuilder();

            // ── Header band ──────────────────────────────────────────────────────
            // Dark navy bar
            s.AppendLine($"{C_NavyRG} rg 0 {PageHeight - HeaderBandHeight} {PageWidth} {HeaderBandHeight} re f");
            // Teal accent stripe (3 pt)
            s.AppendLine($"{C_TealRG} rg 0 {PageHeight - HeaderBandHeight} {PageWidth} 3 re f");
            // Report title in white
            s.AppendLine($"{C_WhiteRG} rg BT /F1 {FontSizeTitle} Tf {MarginLeft} {PageHeight - 42} Td ({EscPdf("AI Cephalometric Analysis")}) Tj ET");
            // Thin white label "REPORT" beside
            s.AppendLine($"0.6 0.72 0.82 rg BT /F1 {FontSizeMuted} Tf {MarginLeft + 226} {PageHeight - 38} Td ({EscPdf("REPORT")}) Tj ET");

            // ── Content ──────────────────────────────────────────────────────────
            var y           = TopContentY;
            var inPanel     = false;
            double panelTop = 0;

            foreach (var block in blocks)
            {
                switch (block.Kind)
                {
                    case BlockKind.PanelStart:
                        inPanel  = true;
                        panelTop = y + 4;
                        y       -= 6;
                        break;

                    case BlockKind.PanelEnd:
                        if (inPanel)
                        {
                            var panelH = panelTop - y + 4;
                            // Fog panel background
                            s.AppendLine($"{C_FogRG} rg {MarginLeft - 8} {y} {ContentWidth + 16} {panelH} re f");
                            // Teal left accent bar (3 pt wide)
                            s.AppendLine($"{C_TealRG} rg {MarginLeft - 8} {y} 3 {panelH} re f");
                            inPanel = false;
                        }
                        y -= 6;
                        break;

                    case BlockKind.Rule:
                        s.AppendLine($"{C_RuleRG} RG 0.5 w {MarginLeft} {y} m {MarginLeft + ContentWidth} {y} l S");
                        y -= 10;
                        break;

                    case BlockKind.Blank:
                        y -= LH_Blank;
                        break;

                    case BlockKind.Title:
                        s.AppendLine($"{C_NavyRG} rg BT /F1 {FontSizeTitle} Tf {MarginLeft} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        y -= LH_Title;
                        break;

                    case BlockKind.Section:
                    {
                        y -= 8; // top padding
                        // Section label pill
                        var labelW = block.Text.Length * 5.8 + 12; // rough estimate
                        s.AppendLine($"{C_NavyRG} rg {MarginLeft - 2} {y - 4} {labelW} 16 re f");
                        s.AppendLine($"{C_WhiteRG} rg BT /F1 {FontSizeSection} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.Text.ToUpperInvariant())}) Tj ET");
                        y -= 20;
                        // Thin rule under section
                        s.AppendLine($"{C_RuleRG} RG 0.4 w {MarginLeft} {y + 2} m {MarginLeft + ContentWidth} {y + 2} l S");
                        y -= 4;
                        break;
                    }

                    case BlockKind.Highlight:
                        // Two-line highlight (skeletal class + vertical pattern side by side)
                        s.AppendLine($"{C_TealRG} rg BT /F1 {FontSizeHighlight} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        y -= LH_Highlight;
                        if (!string.IsNullOrWhiteSpace(block.SecondaryText))
                        {
                            s.AppendLine($"{C_SlateRG} rg BT /F1 {FontSizeHighlight} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.SecondaryText)}) Tj ET");
                            y -= LH_Highlight;
                        }
                        y -= 4;
                        break;

                    case BlockKind.Body:
                        if (!string.IsNullOrWhiteSpace(block.SecondaryText))
                        {
                            // Two-column layout (label left, value right)
                            s.AppendLine($"{C_InkRG} rg BT /F1 {FontSizeBody} Tf {MarginLeft} {y} Td ({EscPdf(block.Text)}) Tj ET");
                            s.AppendLine($"{C_TealRG} rg BT /F1 {FontSizeBody} Tf {MarginLeft + ContentWidth - 80} {y} Td ({EscPdf(block.SecondaryText)}) Tj ET");
                        }
                        else
                        {
                            s.AppendLine($"{C_InkRG} rg BT /F1 {FontSizeBody} Tf {MarginLeft} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        }
                        y -= LH_Body;
                        break;

                    case BlockKind.Muted:
                        s.AppendLine($"{C_SlateRG} rg BT /F1 {FontSizeMuted} Tf {MarginLeft} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        y -= LH_Muted;
                        break;

                    case BlockKind.TableHeader:
                        // Fog background header row
                        s.AppendLine($"{C_NavyRG} rg {MarginLeft - 2} {y - 5} {ContentWidth + 4} 16 re f");
                        s.AppendLine($"{C_WhiteRG} rg BT /F1 {FontSizeTableHeader} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.Text.ToUpperInvariant())}) Tj ET");
                        DrawMeasurementColumns(s, block.SecondaryText, y, true);
                        y -= 18;
                        break;

                    case BlockKind.TableRow:
                        s.AppendLine($"{C_InkRG} rg BT /F1 {FontSizeTableBody} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        DrawMeasurementColumns(s, block.SecondaryText, y, false);
                        y -= 14;
                        break;

                    case BlockKind.TableRowAlt:
                        // Fog stripe
                        s.AppendLine($"{C_FogRG} rg {MarginLeft - 2} {y - 4} {ContentWidth + 4} 14 re f");
                        s.AppendLine($"{C_InkRG} rg BT /F1 {FontSizeTableBody} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        DrawMeasurementColumns(s, block.SecondaryText, y, false);
                        y -= 14;
                        break;

                    case BlockKind.WarningRow:
                        // Amber left bar + body text
                        s.AppendLine($"{C_AmberRG} rg {MarginLeft - 8} {y - 4} 3 14 re f");
                        s.AppendLine($"{C_AmberRG} rg BT /F1 {FontSizeBody} Tf {MarginLeft + 4} {y} Td ({EscPdf("⚠  " + block.Text)}) Tj ET");
                        y -= 15;
                        break;

                    case BlockKind.TreatmentHeader:
                        // Green badge row
                        s.AppendLine($"{C_GreenRG} rg {MarginLeft - 2} {y - 5} {ContentWidth + 4} 17 re f");
                        s.AppendLine($"{C_WhiteRG} rg BT /F1 {FontSizeHighlight} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        y -= 18;
                        break;

                    case BlockKind.TreatmentAlt:
                        // Teal subdued badge row
                        s.AppendLine($"{C_TealRG} rg {MarginLeft - 2} {y - 5} {ContentWidth + 4} 17 re f");
                        s.AppendLine($"{C_WhiteRG} rg BT /F1 {FontSizeHighlight} Tf {MarginLeft + 4} {y} Td ({EscPdf(block.Text)}) Tj ET");
                        y -= 18;
                        break;
                }
            }

            // ── Deferred panel render (safety — closes any un-ended panel) ───────
            // (handled per block above; this is a no-op if panel was closed correctly)

            // ── Footer ───────────────────────────────────────────────────────────
            // Rule above footer
            s.AppendLine($"{C_RuleRG} RG 0.4 w {MarginLeft} {FooterY + 14} m {MarginLeft + ContentWidth} {FooterY + 14} l S");
            // Left: clinic caption
            s.AppendLine($"{C_SlateRG} rg BT /F1 {FontSizeMuted} Tf {MarginLeft} {FooterY} Td ({EscPdf("Generated by DentalCare AI · Cephalometric Analysis Engine")}) Tj ET");
            // Right: page number
            var pageLabel = $"Page {pageNum} of {totalPages}";
            var pageX = MarginLeft + ContentWidth - pageLabel.Length * 4.4; // rough right-align
            s.AppendLine($"{C_SlateRG} rg BT /F1 {FontSizeMuted} Tf {pageX:0.#} {FooterY} Td ({EscPdf(pageLabel)}) Tj ET");

            return StreamObject(s.ToString());
        }

        // ─────────────────────────────────────────────────────────────────────────────
        // Overlay (X-ray landmark image) page
        // ─────────────────────────────────────────────────────────────────────────────

        private static void DrawMeasurementColumns(StringBuilder s, string? packedColumns, double y, bool isHeader)
        {
            if (string.IsNullOrWhiteSpace(packedColumns))
                return;

            var parts = packedColumns.Split('|');
            var value = parts.ElementAtOrDefault(0) ?? "";
            var norm = parts.ElementAtOrDefault(1) ?? "";
            var diff = parts.ElementAtOrDefault(2) ?? "";
            var status = parts.ElementAtOrDefault(3) ?? "";

            var fontSize = isHeader ? FontSizeTableHeader : FontSizeTableBody;
            DrawColumn(value, MarginLeft + 240, isHeader ? C_WhiteRG : C_TealRG);
            DrawColumn(norm, MarginLeft + 315, isHeader ? C_WhiteRG : C_InkRG);
            DrawColumn(diff, MarginLeft + 378, isHeader ? C_WhiteRG : C_SlateRG);
            DrawColumn(status, MarginLeft + 440, isHeader ? C_WhiteRG : StatusColor(status));

            void DrawColumn(string text, double x, string color)
            {
                if (string.IsNullOrWhiteSpace(text))
                    return;

                var display = isHeader ? text.ToUpperInvariant() : text;
                s.AppendLine($"{color} rg BT /F1 {fontSize} Tf {x:0.#} {y} Td ({EscPdf(display)}) Tj ET");
            }
        }

        private static string StatusColor(string status)
        {
            return NormalizeMeasurementStatus(status, "", null) switch
            {
                "Increased" => C_AmberRG,
                "Decreased" => C_TealRG,
                _ => C_GreenRG
            };
        }

        private static byte[] BuildOverlayPageStream(PngPdfImage image)
        {
            const double AvailW = 512.0;
            const double AvailH = 610.0;
            var scale  = Math.Min(AvailW / image.Width, AvailH / image.Height);
            var iw     = image.Width  * scale;
            var ih     = image.Height * scale;
            var ix     = (PageWidth - iw) / 2.0;
            var iy     = 95.0 + (AvailH - ih) / 2.0;

            var s = new StringBuilder();

            // Navy header
            s.AppendLine($"{C_NavyRG} rg 0 {PageHeight - HeaderBandHeight} {PageWidth} {HeaderBandHeight} re f");
            s.AppendLine($"{C_TealRG} rg 0 {PageHeight - HeaderBandHeight} {PageWidth} 3 re f");
            s.AppendLine($"{C_WhiteRG} rg BT /F1 {FontSizeTitle} Tf {MarginLeft} {PageHeight - 42} Td ({EscPdf("X-ray Landmark Overlay")}) Tj ET");
            s.AppendLine($"0.6 0.72 0.82 rg BT /F1 {FontSizeMuted} Tf {MarginLeft + 210} {PageHeight - 38} Td ({EscPdf("AI POINTS + LABELS")}) Tj ET");

            // Fog image card
            s.AppendLine($"{C_FogRG} rg 38 70 536 652 re f");
            // Teal top accent on card
            s.AppendLine($"{C_TealRG} rg 38 {70 + 652 - 4} 536 4 re f");
            // Rule border
            s.AppendLine($"{C_RuleRG} RG 0.6 w 38 70 536 652 re S");

            // Image
            s.AppendLine(FormattableString.Invariant($"q {iw:0.###} 0 0 {ih:0.###} {ix:0.###} {iy:0.###} cm /Im1 Do Q"));

            // Footer
            s.AppendLine($"{C_RuleRG} RG 0.4 w {MarginLeft} {FooterY + 14} m {MarginLeft + ContentWidth} {FooterY + 14} l S");
            s.AppendLine($"{C_SlateRG} rg BT /F1 {FontSizeMuted} Tf {MarginLeft} {FooterY} Td ({EscPdf("AI-generated X-ray overlay with detected cephalometric landmarks. For clinical review only.")}) Tj ET");

            return StreamObject(s.ToString());
        }

        // ─────────────────────────────────────────────────────────────────────────────
        // PNG image object (unchanged from original, well-validated)
        // ─────────────────────────────────────────────────────────────────────────────

        private static byte[] BuildImageObject(PngPdfImage image)
        {
            var colorSpace = image.ColorType switch
            {
                0 => "/DeviceGray",
                2 => "/DeviceRGB",
                3 => BuildIndexedColorSpace(image.Palette),
                _ => "/DeviceRGB"
            };
            var colors     = image.ColorType == 2 ? 3 : 1;
            var decodeParms = $"<< /Predictor 15 /Colors {colors} /BitsPerComponent {image.BitDepth} /Columns {image.Width} >>";
            var header     = Encoding.ASCII.GetBytes(
                $"<< /Type /XObject /Subtype /Image /Width {image.Width} /Height {image.Height} " +
                $"/ColorSpace {colorSpace} /BitsPerComponent {image.BitDepth} " +
                $"/Filter /FlateDecode /DecodeParms {decodeParms} /Length {image.CompressedData.Length} >>\nstream\n");
            var footer = Encoding.ASCII.GetBytes("\nendstream");

            using var ms = new MemoryStream();
            ms.Write(header);
            ms.Write(image.CompressedData);
            ms.Write(footer);
            return ms.ToArray();
        }

        private static PngPdfImage? TryReadPngImage(string? base64)
        {
            if (string.IsNullOrWhiteSpace(base64))
                return null;

            var comma = base64.IndexOf(',');
            if (comma >= 0)
                base64 = base64[(comma + 1)..];

            byte[] bytes;
            try { bytes = Convert.FromBase64String(base64); }
            catch { return null; }

            var sig = new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 };
            if (bytes.Length < 33 || !bytes.Take(sig.Length).SequenceEqual(sig))
                return null;

            var offset = 8;
            int width = 0, height = 0;
            byte bitDepth = 0, colorType = 0;
            byte[]? palette = null;
            using var idat = new MemoryStream();

            while (offset + 8 <= bytes.Length)
            {
                var length = ReadBigEndianInt(bytes, offset);
                var type   = Encoding.ASCII.GetString(bytes, offset + 4, 4);
                offset += 8;
                if (length < 0 || offset + length + 4 > bytes.Length)
                    return null;

                switch (type)
                {
                    case "IHDR":
                        width     = ReadBigEndianInt(bytes, offset);
                        height    = ReadBigEndianInt(bytes, offset + 4);
                        bitDepth  = bytes[offset + 8];
                        colorType = bytes[offset + 9];
                        break;
                    case "IDAT": idat.Write(bytes, offset, length); break;
                    case "PLTE": palette = bytes.Skip(offset).Take(length).ToArray(); break;
                    case "IEND": goto done;
                }
                offset += length + 4;
            }
            done:

            var ok = width > 0 && height > 0 && bitDepth == 8 &&
                     colorType is 0 or 2 or 3 &&
                     (colorType != 3 || (palette?.Length >= 3)) &&
                     idat.Length > 0;
            return ok ? new PngPdfImage(width, height, bitDepth, colorType, idat.ToArray(), palette) : null;
        }

        private static string BuildIndexedColorSpace(byte[]? palette)
        {
            if (palette is null || palette.Length == 0) return "/DeviceRGB";
            var count  = Math.Max(1, palette.Length / 3);
            var hex    = Convert.ToHexString(palette.Take(count * 3).ToArray());
            return $"[/Indexed /DeviceRGB {count - 1} <{hex}>]";
        }

        private static int ReadBigEndianInt(byte[] b, int o)
            => (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3];

        // ─────────────────────────────────────────────────────────────────────────────
        // Text utilities
        // ─────────────────────────────────────────────────────────────────────────────

        private static string NormalizeMeasurementStatus(string? status, string? label, float? difference)
        {
            var combined = $"{status} {label}".ToLowerInvariant();
            if (combined.Contains("increase") || combined.Contains("high") || combined.Contains("protrusive"))
                return "Increased";
            if (combined.Contains("decrease") || combined.Contains("low") || combined.Contains("retrusive"))
                return "Decreased";
            if (difference.HasValue)
            {
                if (difference.Value > 0.5f)
                    return "Increased";
                if (difference.Value < -0.5f)
                    return "Decreased";
            }
            return "Normal";
        }

        private static string InferMeasurementUnit(string measurementName)
        {
            return measurementName.Contains("mm", StringComparison.OrdinalIgnoreCase) ||
                   measurementName.Contains("height", StringComparison.OrdinalIgnoreCase) ||
                   measurementName.Contains("distance", StringComparison.OrdinalIgnoreCase)
                ? "mm"
                : "°";
        }

        private static List<string> WrapText(string text, int maxChars)
        {
            var result = new List<string>();
            if (string.IsNullOrWhiteSpace(text)) return result;

            var words   = text.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            var current = new StringBuilder();

            foreach (var word in words)
            {
                if (current.Length == 0)
                {
                    current.Append(word);
                    continue;
                }
                if (current.Length + word.Length + 1 > maxChars)
                {
                    result.Add(current.ToString());
                    current.Clear().Append(word);
                }
                else
                {
                    current.Append(' ').Append(word);
                }
            }
            if (current.Length > 0)
                result.Add(current.ToString());

            return result;
        }

        private static string Safe(string? value)
        {
            if (string.IsNullOrWhiteSpace(value)) return "";
            var sb = new StringBuilder(value.Length);
            foreach (var ch in value)
            {
                if (ch is >= (char)32 and <= (char)126) sb.Append(ch);
                else if (char.IsWhiteSpace(ch))         sb.Append(' ');
            }
            return sb.ToString();
        }

        private static string ValueOrDefault(string? value, string fallback)
            => string.IsNullOrWhiteSpace(value) ? fallback : Safe(value);

        private static string Truncate(string value, int maxLen)
            => value.Length <= maxLen ? value : value[..Math.Max(0, maxLen - 1)] + "…";

        private static string EscPdf(string value)
            => value
                .Replace("\\", "\\\\")
                .Replace("(", "\\(")
                .Replace(")", "\\)");

        // ─────────────────────────────────────────────────────────────────────────────
        // PDF low-level helpers
        // ─────────────────────────────────────────────────────────────────────────────

        private static byte[] StreamObject(string content)
        {
            var body   = Encoding.ASCII.GetBytes(content);
            var header = Encoding.ASCII.GetBytes($"<< /Length {body.Length} >>\nstream\n");
            var footer = Encoding.ASCII.GetBytes("endstream");

            using var ms = new MemoryStream();
            ms.Write(header);
            ms.Write(body);
            ms.Write(footer);
            return ms.ToArray();
        }

        private static byte[] Ascii(string value)      => Encoding.ASCII.GetBytes(value);
        private static void WriteAscii(Stream s, string v) => s.Write(Encoding.ASCII.GetBytes(v));

        // ─────────────────────────────────────────────────────────────────────────────
        // Internal records
        // ─────────────────────────────────────────────────────────────────────────────

        private sealed record PngPdfImage(
            int    Width,
            int    Height,
            byte   BitDepth,
            byte   ColorType,
            byte[] CompressedData,
            byte[]? Palette);
    }
}
