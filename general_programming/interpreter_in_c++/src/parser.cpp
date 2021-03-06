#include "lexer.h"
#include "parser.h"
#include "ast.h"
#include "token.h"
#include <vector>
#include <sstream>


namespace parser {

    void parser::Parser::NextToken() {
        curToken = peekToken;
        peekToken = l.nextToken();
    };

    Parser New (lexer::Lexer &l) {
        Parser p = {.l = l};
        // Read two tokens, so curToken and peekToken are both set
        p.NextToken();
        p.NextToken();
        return p;
    };

    std::vector<std::string> parser::Parser::Errors() {
        return errors;
    };

    void parser::Parser::PeekError(token::TokenType t) {
        std::ostringstream stream;
        stream << "expected next token to be " << t << ", got " << peekToken.type << " instead";
        errors.push_back(stream.str());
    }

    ast::LetStatement* parser::Parser::ParseLetStatement() {
        ast::LetStatement *s = new ast::LetStatement();
        s->Token = curToken;

        if (!ExpectPeek(token::IDENT)) {
            return nullptr;
        };

        ast::Identifier i = ast::Identifier();
        i.Token = curToken;
        i.Value = curToken.literal;
        s->Name = i;
        if (!ExpectPeek(token::ASSIGN)) {
            return nullptr;
        };

        // TODO - we will skip expressions until
        // we encounter a semicolon
        while (!CurTokenIs(token::SEMICOLON)) {
            NextToken();
        };
        return s;
    };

    ast::ReturnStatement* parser::Parser::ParseReturnStatement() {
        ast::ReturnStatement *s = new ast::ReturnStatement();
        s->Token = curToken;

        NextToken();
        // TODO - we will skip expressions until
        // we encounter a semicolon
        while (!CurTokenIs(token::SEMICOLON)) {
            NextToken();
        };
        return s;
    };

    ast::Statement* parser::Parser::ParseStatement() {
        ast::Statement *s = nullptr;
        if (CurTokenIs(token::LET)) {
            s = ParseLetStatement();
        }
        else if (CurTokenIs(token::RETURN)) {
            s = ParseReturnStatement();
        }
        return s;
    };

    ast::Program* parser::Parser::ParseProgram() {
        ast::Program *program = new ast::Program();
        while (!CurTokenIs(token::ENDOF)) {
            ast::Statement *s = ParseStatement();
            if (s) {
                program->Statements.push_back(s);
            };
            NextToken();
        };
        return program;
    };

    bool parser::Parser::ExpectPeek(token::TokenType t) {
        if (PeekTokenIs(t)) {
            NextToken();
            return true;
        }
        else {
            PeekError(t);
            return false;
        };
    };

    bool parser::Parser::PeekTokenIs(token::TokenType t) {
        return peekToken.type == t;
    };

    bool parser::Parser::CurTokenIs(token::TokenType t) {
        return curToken.type == t;
    }
};
