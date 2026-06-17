namespace DentalCare.Models
{
    public class Patient
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public int Age { get; set; }
        public string Gender { get; set; }
        public string Phone { get; set; }
        public string? Email { get; set; }
        public Guid? CephPatientId { get; set; }
        public List<Appointment> Appointments { get; set; } = new List<Appointment>();
        public List<MedicalRecord> MedicalHistory { get; set; } = new List<MedicalRecord>();
    }
}
