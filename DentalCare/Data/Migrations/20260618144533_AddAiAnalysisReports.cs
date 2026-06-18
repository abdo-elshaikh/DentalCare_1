using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace DentalCare.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddAiAnalysisReports : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<string>(
                name: "Notes",
                table: "MedicalRecord",
                type: "nvarchar(max)",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "nvarchar(max)");

            migrationBuilder.CreateTable(
                name: "AiAnalysisReports",
                columns: table => new
                {
                    Id = table.Column<int>(type: "int", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    PatientId = table.Column<int>(type: "int", nullable: false),
                    MedicalRecordId = table.Column<int>(type: "int", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    DoctorId = table.Column<string>(type: "nvarchar(450)", maxLength: 450, nullable: false),
                    ProtocolId = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: false),
                    ProtocolName = table.Column<string>(type: "nvarchar(200)", maxLength: 200, nullable: false),
                    SkeletalClass = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: false),
                    VerticalPattern = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: false),
                    Summary = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    ConfidenceScore = table.Column<float>(type: "real", nullable: true),
                    ReviewNotes = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    LandmarksJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    MeasurementsJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    MeasurementRowsJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    TreatmentsJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    ClinicalNotesJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    WarningsJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    SkeletalDifferentialJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    OriginalImage = table.Column<byte[]>(type: "varbinary(max)", nullable: true),
                    OriginalImageContentType = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: true),
                    OriginalImageFileName = table.Column<string>(type: "nvarchar(260)", maxLength: 260, nullable: true),
                    OverlayImage = table.Column<byte[]>(type: "varbinary(max)", nullable: true),
                    OverlayImageContentType = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_AiAnalysisReports", x => x.Id);
                    table.ForeignKey(
                        name: "FK_AiAnalysisReports_MedicalRecord_MedicalRecordId",
                        column: x => x.MedicalRecordId,
                        principalTable: "MedicalRecord",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_AiAnalysisReports_Patients_PatientId",
                        column: x => x.PatientId,
                        principalTable: "Patients",
                        principalColumn: "Id");
                });

            migrationBuilder.CreateIndex(
                name: "IX_AiAnalysisReports_MedicalRecordId",
                table: "AiAnalysisReports",
                column: "MedicalRecordId");

            migrationBuilder.CreateIndex(
                name: "IX_AiAnalysisReports_PatientId",
                table: "AiAnalysisReports",
                column: "PatientId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "AiAnalysisReports");

            migrationBuilder.AlterColumn<string>(
                name: "Notes",
                table: "MedicalRecord",
                type: "nvarchar(max)",
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "nvarchar(max)",
                oldNullable: true);
        }
    }
}
