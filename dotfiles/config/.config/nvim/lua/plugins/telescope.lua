return {
	{ "nvim-telescope/telescope-ui-select.nvim" },
	{
		"nvim-telescope/telescope.nvim",
		branch = "0.1.x",
		dependencies = { "nvim-lua/plenary.nvim", "nvim-tree/nvim-web-devicons" },

		config = function()
			local telescope = require("telescope")
			local actions = require("telescope.actions")

			telescope.setup({
				extentions = {
					["ui-select"] = {
						require("telescope.themes").get_dropdown({}),
					},
				},
				defaults = {
					path_display = { "smart" },
					mappings = {
						i = {
							["<C-k>"] = actions.move_selection_previous, -- move to prev result
							["<C-j>"] = actions.move_selection_next, -- move to next result
						},
					},
				},
			})

			telescope.load_extension("ui-select")

			local keymap = vim.keymap

			keymap.set(
				"n",
				"<leader>ff",
				"<CMD>Telescope find_files<CR>",
				{ desc = "Telescope fuzzy find files in cwd" }
			)
			keymap.set("n", "<leader>fr", "<CMD>Telescope oldfiles<CR>", { desc = "Telescope fuzzy find recent files" })
			keymap.set("n", "<leader>fg", "<CMD>Telescope live_grep<CR>", { desc = "Telescope find string in cwd" })
			keymap.set(
				"n",
				"<leader>fc",
				"<CMD>Telescope grep_string<CR>",
				{ desc = "Telescope find string under cursor in cwd" }
			)
		end,
	},
}
