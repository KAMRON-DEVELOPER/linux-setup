return {

	{
		"wallpants/github-preview.nvim",
		cmd = { "GithubPreviewToggle" },
		keys = { "<leader>mpt" },
		opts = {},

		config = function(_, opts)
			local gpreview = require("github-preview")
			gpreview.setup(opts)

			local fns = gpreview.fns
			vim.keymap.set("n", "<leader>mpt", fns.toggle)
			vim.keymap.set("n", "<leader>mps", fns.single_file_toggle)
			vim.keymap.set("n", "<leader>mpd", fns.details_tags_toggle)
		end,
	},

	{
		"MeanderingProgrammer/render-markdown.nvim",
		dependencies = { "nvim-treesitter/nvim-treesitter", "nvim-tree/nvim-web-devicons" },
		-- ---@module 'render-markdown'
		-- ---@type render.md.UserConfig
		opts = {},
	},
}
