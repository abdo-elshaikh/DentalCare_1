using System.ComponentModel.DataAnnotations;

namespace DentalCare.Models
{
    public class AiAnalysisReport
    {
        public int Id { get; set; }

        public int PatientId { get; set; }
        public Patient Patient { get; set; } = null!;

        public int? MedicalRecordId { get; set; }
        public MedicalRecord? MedicalRecord { get; set; }

        [Required]
        public DateTime CreatedAt { get; set; }

        public string DoctorId { get; set; } = string.Empty;

        [Required]
        public string ProtocolId { get; set; } = string.Empty;

        [Required]
        public string ProtocolName { get; set; } = string.Empty;

        public string SkeletalClass { get; set; } = string.Empty;
        public string VerticalPattern { get; set; } = string.Empty;
        public string Summary { get; set; } = string.Empty;
        public float? ConfidenceScore { get; set; }
        public string ReviewNotes { get; set; } = string.Empty;

        public string LandmarksJson { get; set; } = "[]";
        public string MeasurementsJson { get; set; } = "{}";
        public string MeasurementRowsJson { get; set; } = "[]";
        public string TreatmentsJson { get; set; } = "[]";
        public string ClinicalNotesJson { get; set; } = "[]";
        public string WarningsJson { get; set; } = "[]";
        public string SkeletalDifferentialJson { get; set; } = "{}";

        public byte[]? OriginalImage { get; set; }
        public string? OriginalImageContentType { get; set; }
        public string? OriginalImageFileName { get; set; }

        public byte[]? OverlayImage { get; set; }
        public string? OverlayImageContentType { get; set; }
    }
}
