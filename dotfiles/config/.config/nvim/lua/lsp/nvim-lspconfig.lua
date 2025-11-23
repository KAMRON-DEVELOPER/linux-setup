return {
	"neovim/nvim-lspconfig",
	dependencies = {
		-- "saghen/blink.cmp",
		"hrsh7th/cmp-nvim-lsp",
	},

	config = function()
		-- local capabilities = require("blink.cmp").get_lsp_capabilities()
		local capabilities = require("cmp_nvim_lsp").default_capabilities()

		vim.lsp.config("lua_ls", {
			capabilities = capabilities,
			settings = {
				Lua = {
					diagnostics = { globals = { "vim" } },
				},
			},
		})
		vim.lsp.config("bashls", {
			capabilities = capabilities,
		})

		vim.lsp.config("rust_analyzer", {
			capabilities = capabilities,
		})

		vim.lsp.config("pyright", {
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
		vim.lsp.config("rust_analyzer", { capabilities = capabilities })
		vim.lsp.config("gopls", { capabilities = capabilities })
		vim.lsp.config("ts_ls", { capabilities = capabilities })
		-- vim.lsp.config("vtsls", {
		-- 	capabilities = capabilities,
		-- 	settings = {
		-- 		vtsls = {
		-- 			tsserver = {
		-- 				-- globalPlugins = {},
		-- 			},
		-- 		},
		-- 	},
		-- 	filetypes = { "typescript", "javascript", "javascriptreact", "typescriptreact", "vue" },
		-- })
		vim.lsp.config("clangd", { capabilities = capabilities })
		vim.lsp.config("dockerls", { capabilities = capabilities })
		vim.lsp.config("docker_compose_language_service", { capabilities = capabilities })
		vim.lsp.config("jsonls", { capabilities = capabilities })
		vim.lsp.config("taplo", { capabilities = capabilities })

		-- Enable the servers(manually)
		-- vim.lsp.enable("lua_ls")
		-- vim.lsp.enable("rust_analyzer")
		-- vim.lsp.enable("bashls")

		-- local lspconfig = require("lspconfig")
		-- lspconfig.lua_ls.setup({ capabilities = capabilities })
		-- lspconfig.pyright.setup({
		-- 	capabilities = capabilities,
		-- 	on_init = function(client)
		-- 		local cwd = vim.fn.getcwd()
		-- 		local venv_path = cwd .. "/.venv/bin/python"
		--
		-- 		if vim.fn.executable(venv_path) == 1 then
		-- 			client.config.settings.python = { pythonPath = venv_path }
		-- 		else
		-- 			client.config.settings.python = { pythonPath = vim.fn.exepath("python3") }
		-- 		end
		--
		-- 		client.notify("workspace/didChangeConfiguration")
		-- 		return true
		-- 	end,
		-- })
		-- lspconfig.zls.setup({ capabilities = capabilities })
		-- lspconfig.rust_analyzer.setup({ capabilities = capabilities })
		-- lspconfig.gopls.setup({ capabilities = capabilities })
		-- lspconfig.ts_ls.setup({ capabilities = capabilities })
		-- lspconfig.clangd.setup({ capabilities = capabilities })
		-- lspconfig.cmake.setup({ capabilities = capabilities })
		-- lspconfig.dockerls.setup({ capabilities = capabilities })
		-- lspconfig.docker_compose_language_service.setup({ capabilities = capabilities })
		-- lspconfig.jsonls.setup({ capabilities = capabilities })
		-- lspconfig.taplo.setup({ capabilities = capabilities })

		local keymap = vim.keymap

		local rename_function = function()
			vim.lsp.buf.rename()
		end

		-- keymap.set("n", "K", vim.lsp.buf.hover, { desc = "LSP code hovering" })
		keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, { desc = "LSP code action" })
		keymap.set("n", "<leader>cd", vim.lsp.buf.definition, { desc = "LSP code definition" })
		keymap.set("n", "<leader>cr", vim.lsp.buf.references, { desc = "LSP code references" })
		vim.keymap.set("n", "<C-A-l>", vim.lsp.buf.format, { desc = "LSP format buffer" })
		keymap.set("n", "<leader>[d", vim.diagnostic.goto_next, { desc = "Next Diagnostic" })
		keymap.set("n", "<leader>]d", vim.diagnostic.goto_prev, { desc = "Previous Diagnostic" })
		keymap.set("n", "<F2>", rename_function, { desc = "LSP rename" })
	end,
}
