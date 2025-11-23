return {
	{
		"zaldih/themery.nvim",
		lazy = false,
		dependencies = {
			"navarasu/onedark.nvim",
			"folke/tokyonight.nvim",
			"catppuccin/nvim",
			"rose-pine/neovim",
			"ellisonleao/gruvbox.nvim",
		},

		config = function()
			require("themery").setup({
				livePreview = true,

				themes = {
					-- gruvbox
					{
						name = "gruvbox-dark",
						colorscheme = "gruvbox",
						before = [[
              require("gruvbox").setup({
                transparent_mode = false,
                italic = {
                  strings = false,
                  emphasis = false,
                  comments = false,
                  operators = false,
                  folds = false,
                },
              })
              vim.o.background = "dark"
            ]],
					},
					{
						name = "gruvbox-light",
						colorscheme = "gruvbox",
						before = [[
              require("gruvbox").setup({
                transparent_mode = false,
                italic = {
                  strings = false,
                  emphasis = false,
                  comments = false,
                  operators = false,
                  folds = false,
                },
              })
              vim.o.background = "light"
            ]],
					},
					-- onedark
					{
						name = "onedark-dark",
						colorscheme = "onedark",
						before = [[
							require("onedark").setup({
                style = "dark",
                transparent = false,
                lualine = { transparent = false },
              })
							require("onedark").load()
						]],
					},
					{
						name = "onedark-darker",
						colorscheme = "onedark",
						before = [[
							require("onedark").setup({
                style = "darker",
                transparent = false,
                lualine = { transparent = false },
              })
							require("onedark").load()
						]],
					},
					{
						name = "onedark-deep",
						colorscheme = "onedark",
						before = [[
							require("onedark").setup({
                style = "deep",
                transparent = false,
                lualine = { transparent = false },
              })
							require("onedark").load()
						]],
					},
					{
						name = "onedark-warmer",
						colorscheme = "onedark",
						before = [[
							require("onedark").setup({
                style = "warmer",
                transparent = false,
                lualine = { transparent = false },
              })
							require("onedark").load()
						]],
					},
					-- tokyonight
					{
						name = "tokyonight-night",
						colorscheme = "tokyonight",
						before = [[
							require("tokyonight").setup({
                style = "night",
                transparent = false,
                styles = {
		              -- sidebars = "transparent",
		              -- floats = "transparent",
	              }
              })
						]],
					},
					{
						name = "tokyonight-storm",
						colorscheme = "tokyonight",
						before = [[
							require("tokyonight").setup({
                style = "storm",
                transparent = false,
                styles = {
		              -- sidebars = "transparent",
		              -- floats = "transparent",
	              }
              })
						]],
					},
					{
						name = "tokyonight-moon",
						colorscheme = "tokyonight",
						before = [[
							require("tokyonight").setup({
                style = "moon",
                transparent = false,
                styles = {
		              -- sidebars = "transparent",
		              -- floats = "transparent",
	              }
              })
						]],
					},
					{
						name = "tokyonight-day",
						colorscheme = "tokyonight",
						before = [[
							require("tokyonight").setup({
                style = "day",
                transparent = false,
                styles = {
		              -- sidebars = "transparent",
		              -- floats = "transparent",
	              }
              })
						]],
					},
					-- catppuccin
					{
						name = "catppuccin-frappe",
						colorscheme = "catppuccin",
						before = [[
							require("catppuccin").setup({
                flavour = "frappe",
                transparent_background = false,
                show_end_of_buffer = false,
                no_italic = true,
              })
						]],
					},
					{
						name = "catppuccin-macchiato",
						colorscheme = "catppuccin",
						before = [[
							require("catppuccin").setup({
                flavour = "macchiato",
                transparent_background = false,
                show_end_of_buffer = false,
                no_italic = true,
              })
						]],
					},
					{
						name = "catppuccin-mocha",
						colorscheme = "catppuccin",
						before = [[
							require("catppuccin").setup({
                flavour = "mocha",
                transparent_background = false,
                show_end_of_buffer = false,
                no_italic = true,
              })
						]],
					},
					{
						name = "catppuccin-latte",
						colorscheme = "catppuccin",
						before = [[
							require("catppuccin").setup({
                flavour = "latte",
                transparent_background = false,
                show_end_of_buffer = false,
                no_italic = true,
              })
						]],
					},
					-- rose-pine
					{
						name = "rose-pine-main",
						colorscheme = "rose-pine",
						before = [[
              require("rose-pine").setup({
                variant = "main",
                styles = {
                  bold = false,
                  italic = false,
                  transparency = false,
                },
              })
            ]],
					},
					{
						name = "rose-pine-dawn",
						colorscheme = "rose-pine",
						before = [[
            require("rose-pine").setup({
                variant = "dawn",
                styles = {
                  bold = false,
                  italic = false,
                  transparency = false,
                },
              })
            ]],
					},
					{
						name = "rose-pine-moon",
						colorscheme = "rose-pine",
						before = [[
            require("rose-pine").setup({
                variant = "moon",
                styles = {
                  bold = false,
                  italic = false,
                  transparency = false,
                },
              })
            ]],
					},
				},
			})

			vim.keymap.set("n", "<leader>th", ":Themery<CR>", { desc = "Themery" })
		end,
	}
	-- {
	-- 	"xiyaowong/transparent.nvim",
	-- 	config = function()
	-- 		vim.keymap.set("n", "<leader>tt", ":TransparentToggle<CR>", { desc = "Toggle transparent" })
	-- 	end,
	-- },
	-- {
	-- 	"tribela/transparent.nvim",
	-- 	event = "VimEnter",
	-- 	config = true,
	-- },
}
