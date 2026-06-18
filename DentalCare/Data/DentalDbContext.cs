using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;
using DentalCare.Models;

namespace DentalCare.Data
{
    public class DentalDbContext : IdentityDbContext
    {
        public DentalDbContext(DbContextOptions<DentalDbContext> options)
            : base(options)
        {
        }

        public DbSet<Patient> Patients { get; set; }
        public DbSet<Appointment> Appointments { get; set; }
        public DbSet<MedicalRecord> MedicalRecords { get; set; }
        public DbSet<AiAnalysisReport> AiAnalysisReports { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            modelBuilder.Entity<Patient>().Property(p => p.Name).IsRequired().HasMaxLength(100);
            modelBuilder.Entity<MedicalRecord>().ToTable("MedicalRecord");

            modelBuilder.Entity<AiAnalysisReport>(entity =>
            {
                entity.HasOne(r => r.Patient)
                    .WithMany()
                    .HasForeignKey(r => r.PatientId)
                    .OnDelete(DeleteBehavior.NoAction);

                entity.HasOne(r => r.MedicalRecord)
                    .WithMany()
                    .HasForeignKey(r => r.MedicalRecordId)
                    .OnDelete(DeleteBehavior.SetNull);

                entity.Property(r => r.DoctorId).HasMaxLength(450);
                entity.Property(r => r.ProtocolId).HasMaxLength(100);
                entity.Property(r => r.ProtocolName).HasMaxLength(200);
                entity.Property(r => r.SkeletalClass).HasMaxLength(100);
                entity.Property(r => r.VerticalPattern).HasMaxLength(100);
                entity.Property(r => r.OriginalImageContentType).HasMaxLength(100);
                entity.Property(r => r.OriginalImageFileName).HasMaxLength(260);
                entity.Property(r => r.OverlayImageContentType).HasMaxLength(100);
            });
        }
    }
}
