#!/usr/bin/env cabal
{- cabal:
  build-depends: base >= 4.7 && < 5
-}
{-# LANGUAGE DataKinds #-}
{-# LANGUAGE GADTs #-}
{-# LANGUAGE GHC2024 #-}
{-# LANGUAGE KindSignatures #-}
{-# LANGUAGE PolyKinds #-}
{-# LANGUAGE TupleSections #-}
{-# LANGUAGE TypeFamilies #-}
{-# LANGUAGE TypeOperators #-}

import Control.Applicative(Applicative(..))
import Data.Kind (Type)
import Data.Type.Equality ((:~:)(Refl))

type family Append (xs :: [k]) (ys :: [k]) :: [k] where
  Append '[]       ys = ys
  Append (x ': xs) ys = x ': Append xs ys

data MongoFilterType = Simple | Compound

data MongoFilter (t :: MongoFilterType) a where
  StrAttributeEquality
    :: String -- ^ attribute name, no compile time checking
    -> String -- ^ expected value
    -> MongoFilter 'Simple Bool
  NumAttributeEquality
    :: (Num x, Show x)
    => String -- ^ attribute name, no compile time checking
    -> x -- ^ expected value
    -> MongoFilter 'Simple Bool
  MongoAnd :: [MongoFilter x Bool] -> MongoFilter 'Compound Bool
  MongoOr :: [MongoFilter x Bool] -> MongoFilter 'Compound Bool
  MongoAlways :: MongoFilter 'Simple Bool
  MongoNever :: MongoFilter 'Simple Bool

compileSimpleMongoFilter :: MongoFilter 'Simple Bool -> (String, String)
compileSimpleMongoFilter (StrAttributeEquality id val) = ("'$" <> id <> "'", "'" <> val <> "'") -- imagine real JSON quoting here
compileSimpleMongoFilter (NumAttributeEquality id val) = ("'$" <> id <> "'", show val)
compileSimpleMongoFilter MongoAlways = ("true", "true")
compileSimpleMongoFilter MongoNever = ("false", "true")

compileCompoundMongoFilter :: MongoFilter 'Compound Bool -> (String, String)
compileCompoundMongoFilter (MongoAnd mongoAnd) =
  ("$and"
  , "[" <> foldr (\f tl -> let cf = compileMongoFilter f
                            in if cf == "[(\"true\",\"true\")]"
                               then tl
                               else cf <> "," <> tl)
                 ""
                 mongoAnd <> "]")
compileCompoundMongoFilter (MongoOr mongoOr) =
  ("$or"
  , "[" <> foldr (\f tl -> let cf = compileMongoFilter f
                            in if cf == "(\"false\",\"true\")"
                               then tl
                               else cf <> "," <> tl)
                 ""
                 mongoOr <> "]")

compileMongoFilter :: MongoFilter a Bool -> String
compileMongoFilter a@(StrAttributeEquality _ _) = show $ compileSimpleMongoFilter a
compileMongoFilter a@(NumAttributeEquality _ _) = show $ compileSimpleMongoFilter a
compileMongoFilter a@(MongoAnd _) = show $ compileCompoundMongoFilter a
compileMongoFilter a@(MongoOr _) = show $ compileCompoundMongoFilter a
compileMongoFilter a@MongoAlways = show $ compileSimpleMongoFilter a
compileMongoFilter a@MongoNever = show $ compileSimpleMongoFilter a

instance Show (MongoFilter x Bool) where
  show = compileMongoFilter

data QueryType = Single | Many

data SingletonQueryType (qt :: QueryType) where
  SSingle :: SingletonQueryType 'Single
  SMany   :: SingletonQueryType 'Many

instance Show (SingletonQueryType qt) where
  show SSingle = "Single"
  show SMany   = "Many"

data Query (qt :: QueryType) d = Query
  { query          :: MongoFilter 'Compound Bool
  , example_result :: d
  , query_type     :: SingletonQueryType qt
  }
  deriving (Show)

newtype Document d = Document d
  deriving (Show, Eq, Ord)

-- A request records the document type and query-result type.
data Request = Req Type Type

-- | The return types corresponding to a list of queries.
type family FindOneResult (r :: Request) :: Type where
  FindOneResult ('Req (Document _) (Query Single q)) = Maybe q
  FindOneResult ('Req (Document _) (Query Many q)) = [q]

type family FindOneResults (xs :: [Request]) :: [Type] where
  FindOneResults '[]       = '[]
  FindOneResults (r ': xs) = FindOneResult r ': FindOneResults xs

data HList (xs :: [Type]) where
  HOne  :: x -> HList '[x]
  HCons :: x -> HList (y ': ys) -> HList (x ': y ': ys)

data FindOneQueries (xs :: [Request]) where
  FOQOne :: Document d -> Query t q -> FindOneQueries '[ 'Req (Document d) (Query t q) ]
  FOQCons
    :: Document d
    -> Query t q
    -> FindOneQueries (x ': xs)
    -> FindOneQueries ('Req (Document d) (Query t q) ': x ': xs)

deriving instance (Show d, Show q)
  => Show (FindOneQueries '[ 'Req (Document d) (Query t q)])

deriving instance (Show d, Show q, Show (FindOneQueries (x ': xs)))
  => Show (FindOneQueries ('Req (Document d) (Query t q) ': x ': xs))

data MongoLoader a where
  -- | No round-trip to Mongo needed, just return the value
  Pure :: a -> MongoLoader a
  -- | Combination of queries in 1+ collections, each query returning 0-1 documents.
  Roundtrip
    :: FindOneQueries xs
    -> (HList (FindOneResults xs) -> a)
    -> MongoLoader a
  PostProcessed
    :: MongoLoader i -> (i -> a) -> MongoLoader a

instance Functor MongoLoader where
  fmap f (Pure x) = Pure $ f x
  fmap f ml@(Roundtrip _ _) = PostProcessed ml f
  fmap f (PostProcessed ml e) = PostProcessed ml (f . e)

class (Functor a) => Apply a where
  pureM :: v -> a v

instance Apply MongoLoader where
  pureM = Pure

class (Apply a) => Mult a where
  mult :: a l -> a r -> a (l, r)

instance Mult MongoLoader where
  (Pure a) `mult` (Pure b) =
    Pure (a, b)
  (Pure a) `mult` (Roundtrip queries pp) =
    Roundtrip queries $ (a,) . pp
  (Pure a) `mult` (PostProcessed ml pp) =
    PostProcessed ml $ (a,) . pp
  (Roundtrip queries pp) `mult` (Pure b) =
    Roundtrip queries $ (,b) . pp
  (Roundtrip lft_queries lft_pp) `mult` (Roundtrip rgt_queries rgt_pp) =
    Roundtrip (appendQueries lft_queries rgt_queries) $ \results ->
      case appendResultsProof lft_queries rgt_queries of
        Refl ->
          case splitResults lft_queries rgt_queries results of
            (lft_results, rgt_results) ->
              (lft_pp lft_results, rgt_pp rgt_results)
  lft@(Roundtrip _ _) `mult` (PostProcessed ml rgt_pp) =
    PostProcessed (lft `mult` ml)
                $ \(lft, rgt) -> (lft, rgt_pp rgt)
  (PostProcessed ml pp) `mult` (Pure rgt) =
    PostProcessed ml $ (, rgt) . pp
  (PostProcessed ml lft_pp) `mult` rgt@(Roundtrip _ _) =
    PostProcessed (ml `mult` rgt)
                $ \(lft, rgt) -> (lft_pp lft, rgt)
  (PostProcessed lft_ml lft_pp) `mult` (PostProcessed rgt_ml rgt_pp) =
    PostProcessed (lft_ml `mult` rgt_ml)
                $ \(lft, rgt) -> (lft_pp lft, rgt_pp rgt)

multAp f x = (\(ff, xx) -> ff xx) <$> (f `mult` x)

evalMongoLoader :: MongoLoader a -> (String, a)
evalMongoLoader (Pure a) = ("pure", a)
evalMongoLoader (Roundtrip queries pp) = ("Roundtrip", pp $ produceValues queries)
evalMongoLoader (PostProcessed ml pp) =
  let (internalDescription, values) = evalMongoLoader ml
  in ("PostProcessed(" <> internalDescription <> ")", pp values)

produceValues :: FindOneQueries xs -> HList (FindOneResults xs)
produceValues (FOQOne _ (Query _ d SSingle)) = HOne $ Just d
produceValues (FOQOne _ (Query _ d SMany)) = HOne [d]
produceValues (FOQCons _ (Query _ d SSingle) tl) = HCons (Just d) $ produceValues tl
produceValues (FOQCons _ (Query _ d SMany) tl) = HCons [d] $ produceValues tl

appendQueries
  :: FindOneQueries xs
  -> FindOneQueries ys
  -> FindOneQueries (Append xs ys)
appendQueries (FOQOne d q) (FOQOne e r) =
  FOQCons d q (FOQOne e r)
appendQueries (FOQOne d q) (FOQCons e r ys) =
  FOQCons d q (FOQCons e r ys)
appendQueries (FOQCons d q xs) ys =
  FOQCons d q (appendQueries xs ys)

appendResultsProof
  :: FindOneQueries xs
  -> FindOneQueries ys
  -> FindOneResults (Append xs ys)
       :~: Append (FindOneResults xs) (FindOneResults ys)
appendResultsProof (FOQOne _ _) _ = Refl
appendResultsProof (FOQCons _ _ xs) ys =
  case appendResultsProof xs ys of
    Refl -> Refl

splitResults
  :: FindOneQueries xs
  -> FindOneQueries ys
  -> HList (Append (FindOneResults xs) (FindOneResults ys))
  -> (HList (FindOneResults xs), HList (FindOneResults ys))
splitResults (FOQOne _ _) (FOQOne _ _) (HCons x (HOne y)) =
  (HOne x, HOne y)
splitResults (FOQOne _ _) (FOQCons _ _ _) (HCons x rest) =
  (HOne x, rest)
splitResults (FOQCons _ _ xs) ys (HCons x rest) =
  case splitResults xs ys rest of
    (left, right) -> (HCons x left, right)

mkQuery1
  :: forall d. Document d
  -> (MongoFilter 'Compound Bool)
  -> MongoLoader (Maybe d)
mkQuery1 d@(Document doc) q = Roundtrip (FOQOne d (Query q doc SSingle)) pick
  where pick :: HList '[Maybe d] -> Maybe d
        pick (HOne x) = x

mkQueryMany
  :: forall d. Document d
  -> (MongoFilter 'Compound Bool)
  -> MongoLoader [d]
mkQueryMany d@(Document doc) q = Roundtrip (FOQOne d (Query q doc SMany)) pick
  where pick :: HList '[[d]] -> [d]
        pick (HOne x) = x

main :: IO ()
main = do
  let x = pureM (3 :: Int)
  let y = mkQuery1 (Document [("user_id", Just "t@example.com"), ("account_id", Nothing)])
                   (MongoAnd [(StrAttributeEquality "user_id" "t@example.com")])
  let z = mkQuery1 (Document [("pi", 3.14 :: Double), ("e", 2.72), ("i^2", -1)])
                   (MongoAnd [(NumAttributeEquality "pi" 3.14)])
  putStrLn . show $ evalMongoLoader x
  putStrLn . show $ evalMongoLoader $ x `mult` y
  putStrLn . show $ evalMongoLoader $ y `mult` ((*3) <$> x) `mult` ((map ((+1) <$>) <$>) <$> z)
  let user uid = mkQuery1 (Document [("user_id", "t@example.com"), ("account_id", "aaaa")])
                          (MongoAnd [(StrAttributeEquality "user_id" uid)])
  let folder fid aid = mkQuery1 (Document ["folder_id", fid, "name", "some folder", "account_id", aid])
                                (MongoAnd [(StrAttributeEquality "folder_id" fid)])
  let note fid note_id = mkQuery1 (Document [("folder_id", fid), ("note_id", note_id), ("title", "A title")])
                                  (MongoAnd [(StrAttributeEquality "folder_id" fid), (StrAttributeEquality "note_id" note_id)])
  let validateUserForFolder fid = (pureM checkUserHasAccessToFolder `multAp` user "s@test.com" `multAp` folder "ffff" fid)
  let getNote fid = (getNoteIfUserHasAccess <$> validateUserForFolder fid) `multAp` note fid "666000"
  putStrLn . show $ evalMongoLoader (pureM checkUserHasAccessToFolder `multAp` user "s@test.com" `multAp` folder "ffff" "aaaa")
  putStrLn . show $ evalMongoLoader $ getNote "ffff"
  putStrLn . show $ evalMongoLoader $ getNote "eeee"

checkUserHasAccessToFolder :: Maybe [(String, String)] -> Maybe [String] -> Either String Bool
checkUserHasAccessToFolder Nothing _ = Left "No such user"
checkUserHasAccessToFolder _ Nothing = Left "No such folder"
checkUserHasAccessToFolder (Just user) (Just folder) =
  let user_account_id = foldr (\(attr, val) d -> if attr == "account_id" then Just val else d) Nothing user
      folder_account_id = last folder
   in case user_account_id of
    Just aid -> Right $ aid == folder_account_id
    Nothing -> Left "user has no account_id"

getNoteIfUserHasAccess :: (Either String Bool) -> Maybe [(String , String)] -> Either String [(String , String)]
getNoteIfUserHasAccess (Left s) _ = Left s
getNoteIfUserHasAccess (Right False) _ = Left "No access for user"
getNoteIfUserHasAccess (Right True) Nothing = Left "404: no such note"
getNoteIfUserHasAccess (Right True) (Just note) = Right note

-- Local Variables:
-- compile-command: "./Design.hs"
-- End:
