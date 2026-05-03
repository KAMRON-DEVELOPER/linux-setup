return {}
--[[
return {
	"saghen/blink.cmp",
	version = not vim.g.lazyvim_blink_main and "*",
	build = vim.g.lazyvim_blink_main and "cargo build --release",
	dependencies = {
		"rafamadriz/friendly-snippets",
	},

	opts_extend = { "sources.default", "sources.completion.enabled_providers", "sources.compat" },
	lazy = false,

	opts = {
		snippets = {
			expand = function(snippet, _)
				return LazyVim.cmp.expand(snippet)
			end,
		},

		appearance = {
			nerd_font_variant = "mono",
		},

		completion = {
			accept = {
				auto_brackets = {
					enabled = true,
				},
			},
			menu = {
				draw = {
					treesitter = { "lsp" },
					columns = {
						{ "label", "label_description", gap = 1 },
						{ "kind_icon", "kind" },
					},
				},
			},
			documentation = {
				auto_show = true,
				auto_show_delay_ms = 200,
			},
			ghost_text = {
				enabled = vim.g.ai_cmp,
			},
		},

		sources = {
			default = { "lsp", "path", "snippets", "buffer" },
		},

		fuzzy = { implementation = "prefer_rust_with_warning" },

		keymap = {
			preset = "default",

			-- Disable Enter from accepting
			["<CR>"] = false,

			-- Add Ctrl+Enter to accept
			["<C-CR>"] = { "accept", "fallback" },

			-- Separate show completion and documentation controls
			["<C-space>"] = { "show", "fallback" },
			["<C-h>"] = { "show_documentation", "fallback" },
			["<C-g>"] = { "hide_documentation", "fallback" },

			-- Keep defaults here so you don’t need to check docs later
			-- ["<C-space>"] = { "show", "show_documentation", "hide_documentation" },
			["<C-e>"] = { "hide", "fallback" },
			["<C-y>"] = { "select_and_accept", "fallback" },

			["<Up>"] = { "select_prev", "fallback" },
			["<Down>"] = { "select_next", "fallback" },
			["<C-p>"] = { "select_prev", "fallback_to_mappings" },
			["<C-n>"] = { "select_next", "fallback_to_mappings" },

			["<C-b>"] = { "scroll_documentation_up", "fallback" },
			["<C-f>"] = { "scroll_documentation_down", "fallback" },

			["<Tab>"] = { "snippet_forward", "fallback" },
			["<S-Tab>"] = { "snippet_backward", "fallback" },

			["<C-k>"] = { "show_signature", "hide_signature", "fallback" },
		},
	},

	keys = {
		-- chartoggle
		-- {
		-- 	"<C-;>",
		-- 	function()
		-- 		require("blink.chartoggle").toggle_char_eol(";")
		-- 	end,
		-- 	mode = { "n", "v" },
		-- 	desc = "Toggle ; at eol",
		-- },
		-- {
		-- 	",",
		-- 	function()
		-- 		require("blink.chartoggle").toggle_char_eol(",")
		-- 	end,
		-- 	mode = { "n", "v" },
		-- 	desc = "Toggle , at eol",
		-- },

		-- { "<leader>cd", vim.lsp.buf.definition, desc = "LSP code definition", mode = "n" },
		-- { "<leader>cr", vim.lsp.buf.references, desc = "LSP code references", mode = "n" },
		-- { "<leader>ca", vim.lsp.buf.code_action, desc = "LSP code action", mode = "n" },
	},
}
]]
