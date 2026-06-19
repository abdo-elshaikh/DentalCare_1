using Microsoft.AspNetCore.Mvc;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
namespace DentalCare.Models
{
    public class Appointment
    {
        public int Id { get; set; }

        [Remote(
            action: "IsTimeAvailable",
            controller: "Appointment",
            AdditionalFields = nameof(DoctorId) + "," + nameof(PatientId) + "," + nameof(Id),
            ErrorMessage = "This time is already booked for the selected doctor or patient.")]
        public DateTime Date { get; set; }
        public DateTime CreatedAt { get; set; } = DateTime.Now;

        [Required(ErrorMessage = "من فضلك تأكد من اختيار نوع الزيارة من القائمة")]
        [Display(Name = "نوع الزيارة")]
        public string Type { get; set; } = string.Empty; 
        public string Status { get; set; } = "Pending"; 
        public int PatientId { get; set; }

        [Required(ErrorMessage = "من فضلك تأكد من اختيار طبيب من القائمة")]
        [Display(Name = "الطبيب المعالج")] 
        public string DoctorId { get; set; } = string.Empty;
        public Patient? Patient { get; set; }
    }
}
