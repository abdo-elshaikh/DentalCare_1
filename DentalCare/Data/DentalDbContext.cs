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

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            modelBuilder.Entity<Patient>().Property(p => p.Name).IsRequired().HasMaxLength(100);
        }
    }
}
