return {
	{
		"hrsh7th/nvim-cmp",
		event = "InsertEnter",
		dependencies = {
			"hrsh7th/cmp-nvim-lsp", -- for lsp
			"hrsh7th/cmp-buffer", -- source for text in buffer
			"hrsh7th/cmp-path", -- source for file system paths
		},

		config = function()
			local cmp = require("cmp")

			cmp.setup({
				completion = { completeopt = "menu,menuone,preview,noselect" },

				snippet = {
					expand = function(args)
						vim.snippet.expand(args.body) -- For native neovim snippets (Neovim v0.10+)
					end,
				},

				sources = cmp.config.sources({
					{ name = "nvim_lsp" }, -- for lsp
					{ name = "buffer" }, -- text within current buffer
					{ name = "path" }, -- file system paths
					{ name = "render-markdown" },
				}),

				window = {
					-- completion = cmp.config.window.bordered(),
					-- documentation = cmp.config.window.bordered(),
				},

				mapping = cmp.mapping.preset.insert({
					["<C-k>"] = cmp.mapping.select_prev_item(), -- previous suggestion
					["<C-j>"] = cmp.mapping.select_next_item(), -- next suggestion
					["<C-d>"] = cmp.mapping.scroll_docs(-4),
					["<C-u>"] = cmp.mapping.scroll_docs(4),
					["<C-Space>"] = cmp.mapping.complete(), -- show completion suggestions
					["<C-e>"] = cmp.mapping.abort(), -- close completion window
					["<CR>"] = cmp.mapping.confirm({ select = true }),
				}),
			})
		end,
	},
	{
		"neovim/nvim-lspconfig",
		dependencies = { "hrsh7th/cmp-nvim-lsp" },
		lazy = false,

		config = function()
			local capabilities = require("cmp_nvim_lsp").default_capabilities()
			local lspconfig = require("lspconfig")
			local conform = require("conform")

			lspconfig.lua_ls.setup({ capabilities = capabilities })
			lspconfig.pyright.setup({
				capabilities = capabilities,
				on_init = function(client)
					local cwd = vim.fn.getcwd()
					local venv_path = cwd .. "/.venv/bin/python"

					if vim.fn.executable(venv_path) == 1 then
						client.config.settings.python = { pythonPath = venv_path }
					else
						client.config.settings.python = { pythonPath = vim.fn.exepath("python3") }
					end

					client.notify("workspace/didChangeConfiguration")
					return true
				end,
			})
			-- lspconfig.zls.setup({ capabilities = capabilities })
			lspconfig.rust_analyzer.setup({ capabilities = capabilities })
			lspconfig.gopls.setup({ capabilities = capabilities })
			lspconfig.ts_ls.setup({ capabilities = capabilities })
			lspconfig.clangd.setup({ capabilities = capabilities })
			-- lspconfig.cmake.setup({ capabilities = capabilities })
			lspconfig.dockerls.setup({ capabilities = capabilities })
			lspconfig.docker_compose_language_service.setup({ capabilities = capabilities })
			lspconfig.jsonls.setup({ capabilities = capabilities })
			lspconfig.taplo.setup({ capabilities = capabilities })

			local keymap = vim.keymap

			local rename_function = function()
				vim.lsp.buf.rename()
			end

			local conform_format = function()
				conform.format({
					lsp_fallback = true,
					async = false,
					timeout_ms = 3000,
				})
			end

			-- keymap.set("n", "K", vim.lsp.buf.hover, { desc = "LSP code hovering" })
			keymap.set("n", "<leader>cd", vim.lsp.buf.definition, { desc = "LSP code definition" })
			keymap.set("n", "<leader>cr", vim.lsp.buf.references, { desc = "LSP code references" })
			keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, { desc = "LSP code action" })
			keymap.set("n", "cf", vim.lsp.buf.format, { desc = "LSP format current buffer" })
			keymap.set("n", "<leader>[d", vim.diagnostic.goto_next, { desc = "Next Diagnostic" })
			keymap.set("n", "<leader>]d", vim.diagnostic.goto_prev, { desc = "Previous Diagnostic" })
			keymap.set({ "n", "v" }, "<C-f>", conform_format, { desc = "Conform format file" })
			keymap.set("n", "<F2>", rename_function, { desc = "LSP rename" })
		end,
	},
}
