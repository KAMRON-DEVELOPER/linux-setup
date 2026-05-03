-- Lualine has sections as shown below.
-- +-------------------------------------------------+
-- | A | B | C                             X | Y | Z |
-- +-------------------------------------------------+

return {
	"nvim-lualine/lualine.nvim",

	config = function()
		local lualine = require("lualine")

		lualine.setup({
			options = {
				theme = "auto",
				-- theme = "iceberg_dark",
				-- theme = "codedark",
				-- theme = "base16",
				-- theme = "tokyonight",
				-- theme = "gruvbox_dark",
				-- theme = "jellybeans",
				-- theme = "dracula",
				-- theme = "ayu_mirage",
				-- theme = "horizon",
				-- theme = "nord",
				-- theme = "onedark",
				-- theme = "wombat",

				-- component_separators = { left = '', right = '' }, -- beetween
				-- section_separators = { left = "", right = "" }, -- inside
				-- component_separators = { left = "", right = "" }, -- beetween
				-- section_separators = { left = "", right = "" }, -- inside
			},
			always_divide_middle = true,
			sections = {
				lualine_a = {
					"mode",
					-- { "mode", separator = { left = "", right = "" }, right_padding = 2 },
				},
				lualine_b = { "branch" },
				lualine_c = {},
				lualine_x = { "diagnostics", "filesize" },
				lualine_y = { "filename" },
				lualine_z = {
					"location",
					-- { "location", separator = { left = "", right = "" }, left_padding = 2 },
				},
			},
			inactive_sections = {
				lualine_a = { "mode" },
				lualine_b = { "branch" },
				lualine_c = {},
				lualine_x = { "diagnostics", "filesize" },
				lualine_y = { "filename" },
				lualine_z = { "location" },
			},
		})
	end,
}
