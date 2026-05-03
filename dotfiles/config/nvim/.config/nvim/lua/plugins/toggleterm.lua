return {
	"akinsho/toggleterm.nvim",
	version = "*",

	config = function()
		local toggleterm = require("toggleterm")

		toggleterm.setup({
			size = 20,
			open_mapping = [[<c-\>]],
			hide_numbers = true,
			shade_filetypes = {},
			shade_terminals = true,
			shading_factor = 2,
			start_in_insert = true,
			insert_mappings = true,
			persist_size = true,
			direction = "float",
			close_on_exit = true,
			shell = vim.o.shell,
			auto_scroll = true, -- automatically scroll to the bottom on terminal output
			-- This field is only relevant if direction is set to 'float'
			float_opts = {
				border = "curved", -- 'single' | 'double' | 'shadow' | 'curved'
				winblend = 0,
				highlights = {
					border = "Normal",
					background = "Normal",
				},
			},
		})

		local keymap = vim.keymap

		-- Open ToggleTerm in split modes
		keymap.set(
			"n",
			"<leader>tH",
			"<CMD>ToggleTerm size=10 direction=horizontal<CR>",
			{ desc = "Toggleterm Horizontal" }
		)
		keymap.set(
			"n",
			"<leader>tV",
			"<cmd>ToggleTerm size=80 direction=vertical<cr>",
			{ desc = "Toggleterm Vertical" }
		)

		-- Terminal window navigation
		keymap.set("t", "<C-h>", "<CMD>wincmd h<CR>", { desc = "Move to left window", buffer = 0 })
		keymap.set("t", "<C-j>", "<CMD>wincmd j<CR>", { desc = "Move to below window", buffer = 0 })
		keymap.set("t", "<C-k>", "<CMD>wincmd k<CR>", { desc = "Move to above window", buffer = 0 })
		keymap.set("t", "<C-l>", "<CMD>wincmd l<CR>", { desc = "Move to right window", buffer = 0 })

		-- Escape terminal to normal mode + window commands
		keymap.set("t", "<C-w>", "<CMD>wincmd w<CR>", { desc = "Terminal window command prefix", buffer = 0 })
	end,
}
