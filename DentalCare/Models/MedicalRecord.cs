using System.ComponentModel.DataAnnotations;

namespace DentalCare.Models
{
    public class MedicalRecord
    {
        public int Id { get; set; }
        public int PatientId { get; set; }
        public Patient Patient { get; set; } = null!;

        [Required]
        public DateTime Date { get; set; }

        [Required]
        public string VisitType { get; set; } = string.Empty; // Checkup, Followup, Surgery, Xray

        [Required]
        public string Diagnosis { get; set; } = string.Empty;

        public string? Notes { get; set; }

        public string DoctorId { get; set; } = string.Empty;
    }
}
