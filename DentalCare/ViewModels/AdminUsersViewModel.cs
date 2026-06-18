using System.ComponentModel.DataAnnotations;

namespace DentalCare.ViewModels
{
    public class AdminUsersViewModel
    {
        public List<AdminUserRowViewModel> Users { get; set; } = new();
        public List<string> Roles { get; set; } = new();
        public CreateUserViewModel NewUser { get; set; } = new();
        public string? StatusMessage { get; set; }
    }

    public class AdminUserRowViewModel
    {
        public string Id { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string UserName { get; set; } = string.Empty;
        public List<string> Roles { get; set; } = new();
    }

    public class CreateUserViewModel
    {
        [Required]
        [EmailAddress]
        public string Email { get; set; } = string.Empty;

        [Required]
        [DataType(DataType.Password)]
        [StringLength(32, MinimumLength = 8)]
        public string Password { get; set; } = string.Empty;

        [Required]
        public string Role { get; set; } = "Staff";
    }
}
