return {
	"ThePrimeagen/harpoon",

	config = function()
		local mark = require("harpoon.mark")
		local ui = require("harpoon.ui")

		vim.keymap.set("n", "<leader>a", mark.add_file, { desc = "Harpoon: Mark File" })
		vim.keymap.set("n", "<C-e>", ui.toggle_quick_menu, { desc = "Toggle Harpoon Menu" })
    vim.keymap.set("n", "<leader>d", mark.rm_file, { desc = "Harpoon: Remove File" })

		for i = 1, 25 do
			vim.keymap.set("n", "<A-" .. i .. ">", function()
				ui.nav_file(i)
			end, { desc = "Harpoon file " .. i })
		end
	end,
}
