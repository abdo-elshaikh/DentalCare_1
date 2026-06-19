using System.Globalization;
using DentalCare.Models;
using DentalCare.ViewModels;
using QuestPDF.Fluent;
using QuestPDF.Helpers;
using QuestPDF.Infrastructure;

namespace DentalCare.Services
{
    /// <summary>
    /// Builds a professionally styled, multi-page A4 PDF for AI cephalometric analysis reports using QuestPDF.
    /// </summary>
    public static class AiAnalysisPdfBuilder
    {
        // Brand colors
        private static readonly string Navy = "#122144";
        private static readonly string Teal = "#0C8CB2";
        private static readonly string Fog = "#F3F6FA";
        private static readonly string Cloud = "#DEE7F0";
        private static readonly string Slate = "#6A7A90";
        private static readonly string Rule = "#CFD7E2";
        private static readonly string Ink = "#1A2434";
        
        private static readonly string Green = "#0C8863";
        private static readonly string Amber = "#CC7508";
        private static readonly string Indigo = "#4C60D9";
        private static readonly string Red = "#B84A42";

        static AiAnalysisPdfBuilder()
        {
            QuestPDF.Settings.License = LicenseType.Community;
        }

        public static byte[] Build(
            Patient patient,
            AiAnalysisReportRequest report,
            string doctorName,
            DateTime generatedAt)
        {
            var document = Document.Create(container =>
            {
                container.Page(page =>
                {
                    page.Size(PageSizes.A4);
                    page.Margin(0);
                    page.PageColor(Colors.White);
                    page.DefaultTextStyle(x => x.FontSize(10).FontFamily(Fonts.Arial).FontColor(Ink));

                    page.Header().Element(c => ComposeHeader(c, patient, report, doctorName, generatedAt));
                    page.Content().Element(c => ComposeContent(c, patient, report));
                    page.Footer().Element(ComposeFooter);
                });
            });

            return document.GeneratePdf();
        }

        private static void ComposeHeader(IContainer container, Patient patient, AiAnalysisReportRequest report, string doctorName, DateTime generatedAt)
        {
            container.Background(Navy).PaddingVertical(20).PaddingHorizontal(40).Row(row =>
            {
                row.RelativeItem().Column(column =>
                {
                    column.Item().Text("AI Cephalometric Analysis").FontSize(24).FontColor(Colors.White).SemiBold();
                    column.Item().PaddingTop(5).Text(text =>
                    {
                        text.Span($"Generated {generatedAt:dd MMM yyyy HH:mm}  ·  ").FontColor(Rule).FontSize(10);
                        text.Span($"Clinician: {doctorName}  ·  ").FontColor(Rule).FontSize(10);
                        text.Span($"Protocol: {ValueOrDef(report.ProtocolName, "Core Lateral")}").FontColor(Rule).FontSize(10);
                    });
                });

                row.ConstantItem(100).AlignRight().AlignMiddle().Text("REPORT").FontSize(18).FontColor(Teal).Bold().LetterSpacing(0.1f);
            });
        }

        private static void ComposeContent(IContainer container, Patient patient, AiAnalysisReportRequest report)
        {
            container.PaddingVertical(20).PaddingHorizontal(40).Column(column =>
            {
                // Patient Info
                column.Item().PaddingBottom(20).Element(c => ComposePatientInfo(c, patient));

                // Review Status
                column.Item().PaddingBottom(20).Element(c => ComposeReviewStatus(c, report));

                // Diagnosis Summary
                column.Item().PaddingBottom(20).Element(c => ComposeDiagnosisSummary(c, report));

                // Warnings
                if (report.Warnings != null && report.Warnings.Any())
                {
                    column.Item().PaddingBottom(20).Element(c => ComposeWarnings(c, report.Warnings));
                }

                // Image Overlay
                if (!string.IsNullOrWhiteSpace(report.OverlayImageBase64))
                {
                    column.Item().PaddingBottom(20).Element(c => ComposeImageOverlay(c, report.OverlayImageBase64));
                }

                // Measurements
                if ((report.MeasurementRows != null && report.MeasurementRows.Any()) || (report.Measurements != null && report.Measurements.Any()))
                {
                    column.Item().PaddingBottom(20).Element(c => ComposeMeasurementsTable(c, report));
                }

                // Treatments
                if (report.Treatments != null && report.Treatments.Any())
                {
                    column.Item().PaddingBottom(20).Element(c => ComposeTreatments(c, report.Treatments));
                }

                // Disclaimer
                column.Item().PaddingTop(20).BorderTop(1).BorderColor(Rule).PaddingTop(10).Text("Clinical Notice: This report is AI-assisted and must be independently reviewed, validated, and approved by a qualified dental clinician before use in any clinical decision-making.").FontSize(8).FontColor(Slate).Italic();
            });
        }

        private static void ComposePatientInfo(IContainer container, Patient patient)
        {
            container.Column(column =>
            {
                ComposeSectionTitle(column, "Patient Information");
                column.Item().Text(text =>
                {
                    text.Span($"Patient: {patient.Name}").SemiBold();
                    text.Span($"  ·  ID #{patient.Id}");
                });
                column.Item().Text($"Age: {patient.Age} yrs  ·  Gender: {patient.Gender}  ·  Phone: {patient.Phone}");
            });
        }

        private static void ComposeReviewStatus(IContainer container, AiAnalysisReportRequest report)
        {
            container.Column(column =>
            {
                ComposeSectionTitle(column, "Clinical Review");
                
                var bgColor = report.IsDoctorReviewed ? "#E8F5E9" : "#FFF3E0";
                var accentColor = report.IsDoctorReviewed ? Green : Amber;
                var iconText = report.IsDoctorReviewed ? "✓  Doctor reviewed and approved" : "!  Draft AI output — review required";

                column.Item().Background(bgColor).BorderLeft(4).BorderColor(accentColor).Padding(10).Text(iconText).FontColor(Ink);

                if (!string.IsNullOrWhiteSpace(report.ReviewNotes))
                {
                    column.Item().PaddingTop(5).Text($"Notes: {report.ReviewNotes}").FontSize(9).FontColor(Slate);
                }
            });
        }

        private static void ComposeDiagnosisSummary(IContainer container, AiAnalysisReportRequest report)
        {
            container.Column(column =>
            {
                ComposeSectionTitle(column, "Diagnosis Summary");

                column.Item().Background(Cloud).BorderLeft(4).BorderColor(Teal).Padding(15).Column(inner =>
                {
                    inner.Item().PaddingBottom(5).Row(row =>
                    {
                        row.RelativeItem().Text($"Skeletal Class: {ValueOrDef(report.SkeletalClass, "Unclassified")}").SemiBold().FontColor(Navy);
                        row.RelativeItem().Text($"Vertical Pattern: {ValueOrDef(report.VerticalPattern, "Not specified")}").SemiBold().FontColor(Navy);
                    });

                    inner.Item().Text(ValueOrDef(report.Summary, "No clinical summary returned."));
                });
            });
        }

        private static void ComposeWarnings(IContainer container, List<string> warnings)
        {
            container.Column(column =>
            {
                ComposeSectionTitle(column, "Clinical Warnings");

                foreach (var warning in warnings)
                {
                    column.Item().PaddingBottom(5).Background("#FFF3E0").BorderLeft(4).BorderColor(Amber).Padding(10).Text($"!  {warning}");
                }
            });
        }

        private static void ComposeImageOverlay(IContainer container, string base64)
        {
            try
            {
                var comma = base64.IndexOf(',');
                var data = comma >= 0 ? base64.Substring(comma + 1) : base64;
                var bytes = Convert.FromBase64String(data);

                container.Column(column =>
                {
                    ComposeSectionTitle(column, "X-Ray Overlay");
                    // Ensure the image fits nicely on the page
                    column.Item().Background(Fog).Border(1).BorderColor(Rule).Padding(10).AlignCenter().Image(bytes).FitArea();
                    column.Item().PaddingTop(5).AlignCenter().Text("AI-generated landmark overlay. For clinical review only.").FontSize(8).FontColor(Slate);
                });
            }
            catch
            {
                // Ignore invalid image
            }
        }

        private static void ComposeMeasurementsTable(IContainer container, AiAnalysisReportRequest report)
        {
            container.Column(column =>
            {
                ComposeSectionTitle(column, "Cephalometric Measurements");

                column.Item().Table(table =>
                {
                    table.ColumnsDefinition(columns =>
                    {
                        columns.RelativeColumn(3); // Name
                        columns.RelativeColumn(1.7f); // Value
                        columns.RelativeColumn(1.4f); // Norm
                        columns.RelativeColumn(1.2f); // SD
                        columns.RelativeColumn(1.4f); // Diff
                        columns.RelativeColumn(1.7f); // Status
                    });

                    table.Header(header =>
                    {
                        header.Cell().Background(Navy).Padding(5).Text("MEASUREMENT").FontColor(Colors.White).FontSize(8).SemiBold();
                        header.Cell().Background(Navy).Padding(5).Text("VALUE").FontColor(Colors.White).FontSize(8).SemiBold();
                        header.Cell().Background(Navy).Padding(5).Text("NORM").FontColor(Colors.White).FontSize(8).SemiBold();
                        header.Cell().Background(Navy).Padding(5).Text("SD").FontColor(Colors.White).FontSize(8).SemiBold();
                        header.Cell().Background(Navy).Padding(5).Text("DIFF").FontColor(Colors.White).FontSize(8).SemiBold();
                        header.Cell().Background(Navy).Padding(5).Text("STATUS").FontColor(Colors.White).FontSize(8).SemiBold();
                    });

                    if (report.MeasurementRows != null && report.MeasurementRows.Any())
                    {
                        for (int i = 0; i < report.MeasurementRows.Count; i++)
                        {
                            var m = report.MeasurementRows[i];
                            var unit = string.IsNullOrWhiteSpace(m.Unit) ? InferUnit(m.MeasurementName) : m.Unit;
                            var bg = i % 2 == 0 ? Colors.White.ToString() : Fog;
                            
                            var val = $"{m.Value.ToString("0.0", CultureInfo.InvariantCulture)} {unit}";
                            var norm = m.NormalValue.HasValue ? m.NormalValue.Value.ToString("0.0", CultureInfo.InvariantCulture) : "—";
                            var sd = m.StdDeviation.HasValue ? m.StdDeviation.Value.ToString("0.0", CultureInfo.InvariantCulture) : "—";
                            var diff = m.Difference.HasValue ? m.Difference.Value.ToString("+0.0;-0.0;0.0", CultureInfo.InvariantCulture) : "—";
                            var status = NormaliseStatus(m.Status, m.Label, m.Difference);

                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text(text =>
                            {
                                text.Line(m.MeasurementName).FontSize(9);
                                if (!string.IsNullOrWhiteSpace(m.Interpretation))
                                    text.Line(m.Interpretation).FontSize(7).FontColor(Slate);
                            });
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text(val).FontSize(9);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text(norm).FontSize(9).FontColor(Slate);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text(sd).FontSize(9).FontColor(Slate);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text(diff).FontSize(9).FontColor(Slate);
                            
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).PaddingVertical(3).PaddingHorizontal(5).Element(c => DrawStatusPill(c, status));
                        }
                    }
                    else if (report.Measurements != null)
                    {
                        var measurements = report.Measurements.ToList();
                        for (int i = 0; i < measurements.Count; i++)
                        {
                            var m = measurements[i];
                            var unit = InferUnit(m.Key);
                            var bg = i % 2 == 0 ? Colors.White.ToString() : Fog;
                            
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text(m.Key).FontSize(9);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text($"{m.Value.ToString("0.0", CultureInfo.InvariantCulture)} {unit}").FontSize(9);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text("—").FontSize(9).FontColor(Slate);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text("—").FontSize(9).FontColor(Slate);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).Padding(5).Text("—").FontSize(9).FontColor(Slate);
                            table.Cell().Background(bg).BorderBottom(1).BorderColor(Rule).PaddingVertical(3).PaddingHorizontal(5).Element(c => DrawStatusPill(c, "Normal"));
                        }
                    }
                });
            });
        }

        private static void ComposeTreatments(IContainer container, List<AiTreatmentReportItem> treatments)
        {
            container.Column(column =>
            {
                ComposeSectionTitle(column, "Treatment Suggestions");

                foreach (var t in treatments)
                {
                    var isPrimary = t.IsPrimary;
                    var bg = isPrimary ? Green : Teal;
                    var badgeLabel = isPrimary ? "PRIMARY" : "ALTERNATIVE";
                    var duration = t.DurationMonths > 0 ? $"{t.DurationMonths} months" : "Duration TBD";

                    column.Item().PaddingBottom(15).Decoration(decoration =>
                    {
                        decoration.Before().Background(bg).Padding(8).Row(row =>
                        {
                            row.RelativeItem().Text(ValueOrDef(t.TreatmentName, "Treatment Option")).FontColor(Colors.White).SemiBold();
                            row.ConstantItem(120).AlignRight().Text($"{badgeLabel} | {duration}").FontColor(Colors.White).FontSize(8);
                        });

                        decoration.Content().Border(1).BorderTop(0).BorderColor(Rule).Padding(10).Column(inner =>
                        {
                            if (!string.IsNullOrWhiteSpace(t.Description))
                            {
                                inner.Item().PaddingBottom(5).Text($"Description: {t.Description}");
                            }
                            if (!string.IsNullOrWhiteSpace(t.Rationale))
                            {
                                inner.Item().Text($"Rationale: {t.Rationale}").FontColor(Slate).FontSize(9);
                            }
                        });
                    });
                }
            });
        }

        private static void DrawStatusPill(IContainer container, string status)
        {
            var bgColor = StatusBg(status);
            // Render text inside a styled pill
            container.AlignLeft().Background(bgColor).PaddingVertical(2).PaddingHorizontal(6).Text(status.ToUpperInvariant()).FontColor(Colors.White).FontSize(7).SemiBold();
        }

        private static void ComposeFooter(IContainer container)
        {
            container.PaddingHorizontal(40).PaddingBottom(20).Row(row =>
            {
                row.RelativeItem().Text("DentalCare AI  ·  Cephalometric Analysis Engine").FontSize(8).FontColor(Slate);
                row.RelativeItem().AlignRight().Text(x =>
                {
                    x.Span("Page ").FontSize(8).FontColor(Slate);
                    x.CurrentPageNumber().FontSize(8).FontColor(Slate);
                    x.Span(" of ").FontSize(8).FontColor(Slate);
                    x.TotalPages().FontSize(8).FontColor(Slate);
                });
            });
        }

        private static void ComposeSectionTitle(ColumnDescriptor column, string title)
        {
            column.Item().PaddingBottom(10).PaddingTop(10).Row(row =>
            {
                row.AutoItem().Background(Navy).PaddingVertical(3).PaddingHorizontal(10).Text(title.ToUpperInvariant()).FontColor(Colors.White).FontSize(8).SemiBold();
                row.RelativeItem().PaddingTop(8).BorderTop(1).BorderColor(Rule);
            });
        }

        // ─────────────────────────────────────────────────────────────────────────
        // Utility helpers
        // ─────────────────────────────────────────────────────────────────────────

        private static string NormaliseStatus(string? status, string? label, float? difference)
        {
            var combined = $"{status} {label}".ToLowerInvariant();
            if (combined.Contains("severe"))
                return "Severe";
            if (combined.Contains("mild"))
                return "Mild";
            if (combined.Contains("increase") || combined.Contains("high") || combined.Contains("protrusive"))
                return "Increased";
            if (combined.Contains("decrease") || combined.Contains("low") || combined.Contains("retrusive"))
                return "Decreased";
            if (difference.HasValue)
            {
                if (difference.Value >  0.5f) return "Increased";
                if (difference.Value < -0.5f) return "Decreased";
            }
            return "Normal";
        }

        private static string StatusBg(string status) => status switch
        {
            "Severe" => Red,
            "Mild" => Amber,
            "Increased" => Amber,
            "Decreased" => Indigo,
            _           => Green,
        };

        private static string InferUnit(string name) =>
            name.Contains("mm", StringComparison.OrdinalIgnoreCase) ||
            name.Contains("height", StringComparison.OrdinalIgnoreCase) ||
            name.Contains("distance", StringComparison.OrdinalIgnoreCase) ? "mm" : "°";

        private static string ValueOrDef(string? v, string fallback)
            => string.IsNullOrWhiteSpace(v) ? fallback : v.Trim();
    }
}
