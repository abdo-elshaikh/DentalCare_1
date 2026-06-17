namespace DentalCare.ViewModels
{
    public class AiAnalysisReportRequest
    {
        public int PatientId { get; set; }
        public string SkeletalClass { get; set; } = "";
        public string VerticalPattern { get; set; } = "";
        public string Summary { get; set; } = "";
        public string ProtocolId { get; set; } = "core_lateral";
        public string ProtocolName { get; set; } = "Core Lateral Screening";
        public float? ConfidenceScore { get; set; }
        public List<AiLandmarkReportItem> Landmarks { get; set; } = new();
        public List<string> ClinicalNotes { get; set; } = new();
        public Dictionary<string, float> SkeletalDifferential { get; set; } = new();
        public List<string> Warnings { get; set; } = new();
        public Dictionary<string, float> Measurements { get; set; } = new();
        public List<AiMeasurementReportItem> MeasurementRows { get; set; } = new();
        public List<AiTreatmentReportItem> Treatments { get; set; } = new();
        public string? OverlayImageBase64 { get; set; }
        public bool IsDoctorReviewed { get; set; }
        public string ReviewNotes { get; set; } = "";
    }

    public class AiLandmarkReportItem
    {
        public string Name { get; set; } = "";
        public double X { get; set; }
        public double Y { get; set; }
        public double? Confidence { get; set; }
        public string Provenance { get; set; } = "ai";
        public double? ExpectedErrorMm { get; set; }
    }

    public class AiMeasurementReportItem
    {
        public string MeasurementName { get; set; } = "";
        public float Value { get; set; }
        public string Unit { get; set; } = "";
        public float? NormalValue { get; set; }
        public float? StdDeviation { get; set; }
        public float? Difference { get; set; }
        public string Status { get; set; } = "";
        public string Label { get; set; } = "";
        public string Interpretation { get; set; } = "";
    }

    public class AiTreatmentReportItem
    {
        public string TreatmentName { get; set; } = "";
        public string TreatmentType { get; set; } = "";
        public string Description { get; set; } = "";
        public string Rationale { get; set; } = "";
        public string Risks { get; set; } = "";
        public int DurationMonths { get; set; }
        public float? ConfidenceScore { get; set; }
        public bool IsPrimary { get; set; }
        public string EvidenceLevel { get; set; } = "";
        public string EvidenceReference { get; set; } = "";
        public string RetentionRecommendation { get; set; } = "";
        public float? SuccessProbability { get; set; }
    }

    public class AiGrowthAssessmentRequest
    {
        public int PatientAge { get; set; } = 25;
        public string PatientSex { get; set; } = "Male";
        public int? CvmStage { get; set; }
        public float PxToMm { get; set; } = 1.0f;
        public List<AiLandmarkReportItem> Landmarks { get; set; } = new();
    }

    public class AiExplainDecisionRequest
    {
        public string SkeletalClass { get; set; } = "Class I";
        public string VerticalPattern { get; set; } = "Normodivergent";
        public Dictionary<string, float> Measurements { get; set; } = new();
        public string TreatmentName { get; set; } = "Standard care";
        public Dictionary<string, float> SkeletalDifferential { get; set; } = new();
        public float? SuccessProbability { get; set; }
        public List<string> UncertaintyLandmarks { get; set; } = new();
    }

    public class AiRecalculateAnalysisRequest
    {
        public string ImageBase64 { get; set; } = "";
        public string ImageContentType { get; set; } = "image/jpeg";
        public float PxToMm { get; set; } = 1.0f;
        public string EthnicProfile { get; set; } = "Caucasian";
        public int PatientAge { get; set; } = 25;
        public string PatientSex { get; set; } = "Male";
        public string ProtocolId { get; set; } = "core_lateral";
        public List<AiLandmarkReportItem> Landmarks { get; set; } = new();
    }
}
