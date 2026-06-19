using System.ComponentModel.DataAnnotations;

namespace DentalCare.Models
{
    public class Patient
    {
        public int Id { get; set; }

        [Required(ErrorMessage = "Full name is required.")]
        [StringLength(100, MinimumLength = 2, ErrorMessage = "Full name must be between 2 and 100 characters.")]
        public string Name { get; set; } = string.Empty;

        [Range(5, 80, ErrorMessage = "Age must be between 5 and 80.")]
        public int Age { get; set; }

        [Required(ErrorMessage = "Gender is required.")]
        [RegularExpression("^(Male|Female)$", ErrorMessage = "Please select a valid gender.")]
        public string Gender { get; set; } = string.Empty;

        [Required(ErrorMessage = "Phone number is required.")]
        [Phone(ErrorMessage = "Enter a valid phone number.")]
        [StringLength(11, MinimumLength = 11, ErrorMessage = "Phone number must be exactly 11 characters.")]
        public string Phone { get; set; } = string.Empty;

        [EmailAddress(ErrorMessage = "Enter a valid email address.")]
        [StringLength(254, ErrorMessage = "Email address cannot exceed 254 characters.")]
        public string? Email { get; set; }
        public Guid? CephPatientId { get; set; }
        public List<Appointment> Appointments { get; set; } = new List<Appointment>();
        public List<MedicalRecord> MedicalHistory { get; set; } = new List<MedicalRecord>();
    }
}
