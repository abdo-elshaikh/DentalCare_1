using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace DentalCare.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddCephPatientId : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "CephPatientId",
                table: "Patients",
                type: "uniqueidentifier",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "CephPatientId",
                table: "Patients");
        }
    }
}
