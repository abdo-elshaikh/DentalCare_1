using DentalCare.ViewModels;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace DentalCare.Controllers
{
    [Authorize(Roles = "Admin")]
    public class AdminController : Controller
    {
        private static readonly string[] ClinicRoles = { "Admin", "Doctor", "Staff" };
        private readonly UserManager<IdentityUser> _userManager;

        public AdminController(UserManager<IdentityUser> userManager)
        {
            _userManager = userManager;
        }

        public async Task<IActionResult> Users()
        {
            return View(await BuildUsersViewModelAsync());
        }

        [HttpPost]
        public async Task<IActionResult> CreateUser([Bind(Prefix = "NewUser")] CreateUserViewModel newUser)
        {
            if (!ClinicRoles.Contains(newUser.Role))
                ModelState.AddModelError(nameof(newUser.Role), "Select a valid clinic role.");

            if (!ModelState.IsValid)
                return View("Users", await BuildUsersViewModelAsync(newUser));

            var user = new IdentityUser
            {
                UserName = newUser.Email,
                Email = newUser.Email,
                EmailConfirmed = true
            };

            var result = await _userManager.CreateAsync(user, newUser.Password);
            if (result.Succeeded)
            {
                await _userManager.AddToRoleAsync(user, newUser.Role);
                TempData["StatusMessage"] = $"Created {newUser.Email} as {newUser.Role}.";
                return RedirectToAction(nameof(Users));
            }

            foreach (var error in result.Errors)
                ModelState.AddModelError(string.Empty, error.Description);

            return View("Users", await BuildUsersViewModelAsync(newUser));
        }

        [HttpPost]
        public async Task<IActionResult> UpdateRole(string userId, string role)
        {
            if (!ClinicRoles.Contains(role))
            {
                TempData["StatusMessage"] = "Select a valid clinic role.";
                return RedirectToAction(nameof(Users));
            }

            var user = await _userManager.FindByIdAsync(userId);
            if (user == null) return NotFound();

            if (await IsLastAdminAsync(user) && role != "Admin")
            {
                TempData["StatusMessage"] = "You cannot remove the last Admin user.";
                return RedirectToAction(nameof(Users));
            }

            var currentRoles = await _userManager.GetRolesAsync(user);
            var removeResult = await _userManager.RemoveFromRolesAsync(user, currentRoles);
            if (!removeResult.Succeeded)
            {
                TempData["StatusMessage"] = "Could not update user roles.";
                return RedirectToAction(nameof(Users));
            }

            var addResult = await _userManager.AddToRoleAsync(user, role);
            TempData["StatusMessage"] = addResult.Succeeded
                ? $"Updated {user.Email} to {role}."
                : "Could not assign the selected role.";
            return RedirectToAction(nameof(Users));
        }

        [HttpPost]
        public async Task<IActionResult> DeleteUser(string userId)
        {
            var user = await _userManager.FindByIdAsync(userId);
            if (user == null) return NotFound();

            var currentUserId = _userManager.GetUserId(User);
            if (user.Id == currentUserId)
            {
                TempData["StatusMessage"] = "You cannot delete your own account.";
                return RedirectToAction(nameof(Users));
            }

            if (await IsLastAdminAsync(user))
            {
                TempData["StatusMessage"] = "You cannot delete the last Admin user.";
                return RedirectToAction(nameof(Users));
            }

            var result = await _userManager.DeleteAsync(user);
            TempData["StatusMessage"] = result.Succeeded
                ? $"Deleted {user.Email}."
                : "Could not delete the user.";
            return RedirectToAction(nameof(Users));
        }

        private async Task<AdminUsersViewModel> BuildUsersViewModelAsync(CreateUserViewModel? newUser = null)
        {
            var users = await _userManager.Users
                .OrderBy(u => u.Email)
                .ToListAsync();

            var rows = new List<AdminUserRowViewModel>();
            foreach (var user in users)
            {
                rows.Add(new AdminUserRowViewModel
                {
                    Id = user.Id,
                    Email = user.Email ?? "",
                    UserName = user.UserName ?? "",
                    Roles = (await _userManager.GetRolesAsync(user)).OrderBy(r => r).ToList()
                });
            }

            return new AdminUsersViewModel
            {
                Users = rows,
                Roles = ClinicRoles.ToList(),
                NewUser = newUser ?? new CreateUserViewModel(),
                StatusMessage = TempData["StatusMessage"] as string
            };
        }

        private async Task<bool> IsLastAdminAsync(IdentityUser user)
        {
            if (!await _userManager.IsInRoleAsync(user, "Admin"))
                return false;

            var admins = await _userManager.GetUsersInRoleAsync("Admin");
            return admins.Count <= 1;
        }
    }
}
