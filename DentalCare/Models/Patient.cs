namespace DentalCare.Models
{
    public class Patient
    {
        public int Id { get; set; }
        public string Name { get; set; } = string.Empty;
        public int Age { get; set; }
        public string Gender { get; set; } = string.Empty;
        public string Phone { get; set; } = string.Empty;
        public string? Email { get; set; }
        public Guid? CephPatientId { get; set; }
        public List<Appointment> Appointments { get; set; } = new List<Appointment>();
        public List<MedicalRecord> MedicalHistory { get; set; } = new List<MedicalRecord>();
    }
}
