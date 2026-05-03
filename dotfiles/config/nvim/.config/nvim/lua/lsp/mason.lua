return {
	{
		"williamboman/mason.nvim",
		dependencies = {
			"WhoIsSethDaniel/mason-tool-installer.nvim",
		},

		config = function()
			local mason = require("mason")
			local mason_tool_installer = require("mason-tool-installer")

			mason.setup({
				ui = {
					icons = {
						package_installed = "✓",
						package_pending = "➜",
						package_uninstalled = "✗",
					},
				},
			})

			mason_tool_installer.setup({
				ensure_installed = {
					-- "lua-language-server", -- lsp (lua), mason-lspconfig (lua_ls)
					"stylua", -- formatter (lua)
					"pyright", -- lsp (python)
					"mypy", -- linter (python)
					-- "ruff", -- lsp, linter, formatter (python)
					"isort", -- formatter (python)
					"black", -- formatter (python)
					-- "zls", -- formatter (zig)
					-- "rust-analyzer", -- lsp (rust)
					-- "rustfmt", -- formatter (rust), comes with rust
					-- "gopls",                      -- lsp (go), official go language server (pronounced "Go please")
					-- "gofumpt",                    -- formatter (go), a stricter gofmt
					-- "goimports", -- formatter (go), formats like gofmt and fix imports
					-- "typescript-language-server", -- lsp (javascript and typescript), mason-lspconfig (ts_ls)
					-- "vtsls",
					-- "quick-lint-js",              -- lsp (javascript and typescript), 130x faster than ESlint
					"prettier", -- formatter (javascript, typescript, json, html, JSX, markdown, yaml)
					-- "clangd",                     -- lsp (C and C++)
					-- "clang-format",               -- formatter (c, c++)
					-- "cmake-language-server",      -- lsp (cmake), mason-lspconfig (cmake)
					-- "cmakelint",                  -- linter (cmake)
					-- "gersemi",                    -- formatter (cmake)
					-- "dockerfile-language-server", -- lsp (docker), mason-slpconfig (dockerls)
					-- "docker-compose-language-service", -- lsp (docker compose), mason-lspconfig (docker_compose_language_service)
					-- "json-lsp", -- lsp (json), mason-slpconfig (jsonls)
					"taplo", -- lsp (toml)
				},
			})
		end,
	},
	{
		"williamboman/mason-lspconfig.nvim",
		lazy = false,
		config = function()
			local mason_lspconfig = require("mason-lspconfig")

			mason_lspconfig.setup({
				automatic_enable = {
					exclude = {
						"stylua",
            "vtsls"
					},
				},
				-- automatic_enable = false,
				ensure_installed = {
					"lua_ls",
					"pyright",
					"ruff",
					"zls",
					"rust_analyzer",
					"gopls",
					"ts_ls", -- "quick_lint_js",
					-- "vtsls",
					"clangd",
					"cmake",
					"dockerls",
					"docker_compose_language_service",
					"jsonls",
					"taplo",
				},
			})
		end,
	},
}
