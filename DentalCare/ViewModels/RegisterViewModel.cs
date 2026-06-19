using System.ComponentModel.DataAnnotations;

namespace DentalCare.ViewModels
{
    public class RegisterViewModel
    {
        [Required(ErrorMessage = "Enter your work email address.")]
        [EmailAddress(ErrorMessage = "Enter a valid email address.")]
        [Display(Name = "Work email address")]
        public string Email { get; set; } = string.Empty;

        [Required(ErrorMessage = "Create a password.")]
        [StringLength(32, ErrorMessage = "Use between {2} and {1} characters.", MinimumLength = 8)]
        [DataType(DataType.Password)]
        [RegularExpression(@"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\da-zA-Z]).{8,}$", ErrorMessage = "Include uppercase and lowercase letters, a number, and a symbol.")]
        [Display(Name = "Password")]
        public string Password { get; set; } = string.Empty;

        [DataType(DataType.Password)]
        [Display(Name = "Confirm password")]
        [Compare("Password", ErrorMessage = "The passwords do not match.")]
        public string ConfirmPassword { get; set; } = string.Empty;
    }
}
